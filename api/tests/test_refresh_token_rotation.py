import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from database.pg.models import RefreshToken, UsedRefreshToken  # noqa: E402
from database.pg.token_ops import refresh_token_crud  # noqa: E402

_ORIGINAL_WORKING_DIRECTORY = Path.cwd()
os.chdir(Path(__file__).resolve().parents[1] / "app")
try:
    from routers import users
finally:
    os.chdir(_ORIGINAL_WORKING_DIRECTORY)


class _Result:
    def __init__(self, token):
        self.token = token

    def scalar_one_or_none(self):
        return self.token


class _Transaction:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        self.session.in_transaction = True
        self.session.events.append("transaction_enter")

    async def __aexit__(self, exc_type, exc, traceback):
        self.session.events.append("transaction_exit")
        self.session.in_transaction = False


class _Session:
    def __init__(self, returned_token):
        self.returned_token = returned_token
        self.events = []
        self.statements = []
        self.added = []
        self.in_transaction = False
        self.engine = None
        self.expire_on_commit = None

    def factory(self, engine, *, expire_on_commit):
        self.engine = engine
        self.expire_on_commit = expire_on_commit
        return self

    async def __aenter__(self):
        self.events.append("session_enter")
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        self.events.append("session_exit")

    def begin(self):
        return _Transaction(self)

    async def exec(self, statement):
        assert self.in_transaction
        self.events.append("exec")
        self.statements.append(statement)
        return _Result(self.returned_token)

    def add(self, value):
        assert self.in_transaction
        self.events.append("add")
        self.added.append(value)


def _active_token() -> RefreshToken:
    return RefreshToken(
        user_id=uuid.uuid4(),
        token="shared-refresh-token",
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )


def test_consume_refresh_token_deletes_and_records_used_token_in_one_transaction(monkeypatch):
    active_token = _active_token()
    session = _Session(active_token)
    monkeypatch.setattr(refresh_token_crud, "AsyncSession", session.factory)

    consumed = asyncio.run(
        refresh_token_crud.consume_db_refresh_token("engine", active_token.token)
    )

    assert consumed is active_token
    assert session.engine == "engine"
    assert session.expire_on_commit is False
    assert session.events == [
        "session_enter",
        "transaction_enter",
        "exec",
        "add",
        "transaction_exit",
        "session_exit",
    ]
    assert len(session.statements) == 1
    compiled = str(
        session.statements[0].compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )
    assert compiled.startswith("DELETE FROM refresh_tokens")
    assert "WHERE refresh_tokens.token = 'shared-refresh-token'" in compiled
    assert "RETURNING refresh_tokens.id" in compiled

    assert len(session.added) == 1
    used_token = session.added[0]
    assert isinstance(used_token, UsedRefreshToken)
    assert used_token.token == active_token.token
    assert used_token.user_id == active_token.user_id
    assert used_token.expires_at == active_token.expires_at


def test_consume_refresh_token_returns_none_without_recording_used_token(monkeypatch):
    session = _Session(None)
    monkeypatch.setattr(refresh_token_crud, "AsyncSession", session.factory)

    consumed = asyncio.run(
        refresh_token_crud.consume_db_refresh_token("engine", "missing-refresh-token")
    )

    assert consumed is None
    assert len(session.statements) == 1
    assert session.added == []
    assert session.events == [
        "session_enter",
        "transaction_enter",
        "exec",
        "transaction_exit",
        "session_exit",
    ]


def test_concurrent_refresh_attempts_have_one_success_and_one_replay(monkeypatch):
    async def run_attempts():
        active_token = _active_token()
        user = SimpleNamespace(id=active_token.user_id)
        both_arrived = asyncio.Event()
        consume_lock = asyncio.Lock()
        consumed = False
        calls = {
            "consume": 0,
            "theft": 0,
            "get_user": 0,
            "suspension": 0,
            "access": 0,
            "refresh": 0,
        }

        async def fake_consume(engine, token):
            nonlocal consumed
            assert engine == "engine"
            assert token == active_token.token
            async with consume_lock:
                calls["consume"] += 1
                if calls["consume"] == 2:
                    both_arrived.set()

            await asyncio.wait_for(both_arrived.wait(), timeout=1)

            async with consume_lock:
                if consumed:
                    return None
                consumed = True
                return active_token

        async def fake_handle_theft(engine, token):
            assert engine == "engine"
            assert token == active_token.token
            calls["theft"] += 1

        async def fake_get_user(engine, user_id):
            assert engine == "engine"
            assert user_id == str(active_token.user_id)
            calls["get_user"] += 1
            return user

        def fake_raise_if_suspended(db_user):
            assert db_user is user
            calls["suspension"] += 1

        def fake_create_access_token(*, data):
            assert data == {"sub": str(active_token.user_id)}
            calls["access"] += 1
            return "new-access-token"

        async def fake_create_refresh_token(engine, user_id):
            assert engine == "engine"
            assert user_id == str(active_token.user_id)
            calls["refresh"] += 1
            return "new-refresh-token"

        monkeypatch.setattr(users, "consume_db_refresh_token", fake_consume)
        monkeypatch.setattr(users, "handle_refresh_token_theft", fake_handle_theft)
        monkeypatch.setattr(users, "get_user_by_id", fake_get_user)
        monkeypatch.setattr(users, "raise_if_user_suspended", fake_raise_if_suspended)
        monkeypatch.setattr(users, "create_access_token", fake_create_access_token)
        monkeypatch.setattr(users, "create_refresh_token", fake_create_refresh_token)

        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pg_engine="engine")))
        body = users.RefreshRequest(refreshToken=active_token.token)
        results = await asyncio.gather(
            users.refresh_access_token.__wrapped__(request, body),
            users.refresh_access_token.__wrapped__(request, body),
            return_exceptions=True,
        )

        successes = [result for result in results if isinstance(result, users.TokenResponse)]
        failures = [result for result in results if isinstance(result, HTTPException)]

        assert len(successes) == 1
        assert successes[0].accessToken == "new-access-token"
        assert successes[0].refreshToken == "new-refresh-token"
        assert len(failures) == 1
        assert failures[0].status_code == 401
        assert failures[0].detail == "Invalid or expired refresh token"
        assert calls == {
            "consume": 2,
            "theft": 1,
            "get_user": 1,
            "suspension": 1,
            "access": 1,
            "refresh": 1,
        }

    asyncio.run(run_attempts())
