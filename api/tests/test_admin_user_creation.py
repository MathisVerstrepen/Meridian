import asyncio
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from database.pg import models as pg_models
from database.pg.models import create_initial_users
from models.auth import UserPass
from services.admin_user_creation import (
    AdminUserCreationMode,
    parse_admin_user_creation_mode,
    should_create_account_as_admin,
    should_create_initial_userpass_as_admin,
)


class _FakeResult:
    def scalar_one_or_none(self):
        return None


class _FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeSession:
    def __init__(self, engine):
        self.engine = engine

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def begin(self):
        return _FakeTransaction()

    async def execute(self, stmt):
        return _FakeResult()

    def add(self, obj):
        pass

    async def flush(self):
        pass

    async def refresh(self, obj):
        pass


def test_parse_admin_user_creation_mode_defaults_to_first():
    assert parse_admin_user_creation_mode(None) is AdminUserCreationMode.FIRST


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", AdminUserCreationMode.NONE),
        ("first", AdminUserCreationMode.FIRST),
        ("all_userpass", AdminUserCreationMode.ALL_USERPASS),
        ("all", AdminUserCreationMode.ALL),
    ],
)
def test_parse_admin_user_creation_mode_values(value, expected):
    assert parse_admin_user_creation_mode(value) is expected


def test_parse_admin_user_creation_mode_rejects_unknown_value():
    with pytest.raises(ValueError, match="Invalid ADMIN_USER_CREATION"):
        parse_admin_user_creation_mode("invalid")


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        (AdminUserCreationMode.NONE, [False, False]),
        (AdminUserCreationMode.FIRST, [True, False]),
        (AdminUserCreationMode.ALL_USERPASS, [True, True]),
        (AdminUserCreationMode.ALL, [True, True]),
    ],
)
def test_should_create_initial_userpass_as_admin(mode, expected):
    assert [should_create_initial_userpass_as_admin(mode, index) for index in range(2)] == expected


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        (AdminUserCreationMode.NONE, False),
        (AdminUserCreationMode.FIRST, False),
        (AdminUserCreationMode.ALL_USERPASS, False),
        (AdminUserCreationMode.ALL, True),
    ],
)
def test_should_create_account_as_admin(mode, expected):
    assert should_create_account_as_admin(mode) is expected


def test_create_initial_users_marks_first_userpass_admin(monkeypatch):
    monkeypatch.setattr(pg_models, "AsyncSession", _FakeSession)

    users = asyncio.run(
        create_initial_users(
            object(),
            [
                UserPass(username="admin", password="hashed-admin"),
                UserPass(username="user", password="hashed-user"),
            ],
            AdminUserCreationMode.FIRST,
        )
    )

    assert [user.is_admin for user in users] == [True, False]
