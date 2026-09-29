import asyncio
import importlib
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

# Load application modules after adding the repository's source directory.
pg_models = importlib.import_module("database.pg.models")
graph_crud = importlib.import_module("database.pg.graph_ops.graph_crud")
prompt_improver_crud = importlib.import_module(
    "database.pg.prompt_improver_ops.prompt_improver_crud"
)
provider_token_crud = importlib.import_module("database.pg.token_ops.provider_token_crud")
refresh_token_crud = importlib.import_module("database.pg.token_ops.refresh_token_crud")
usage_crud = importlib.import_module("database.pg.user_ops.usage_crud")
user_crud = importlib.import_module("database.pg.user_ops.user_crud")
auth = importlib.import_module("models.auth")
users_dto = importlib.import_module("models.usersDTO")
admin_user_creation = importlib.import_module("services.admin_user_creation")


@pytest.fixture
def session():
    session = MagicMock()
    session.__aenter__.return_value = session
    session.__aexit__.return_value = False
    session.begin.return_value.__aexit__.return_value = False
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    result.first.return_value = None
    result.scalars.return_value.first.return_value = None
    session.exec = AsyncMock(return_value=result)
    session.execute = AsyncMock(return_value=result)
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.mark.parametrize("kind", ["refresh", "provider"])
@pytest.mark.parametrize("valid", [True, False])
def test_token_creation_parses_owner_before_persistence(monkeypatch, session, kind, valid):
    owner = uuid.uuid4()
    user_id = str(owner) if valid else "not-a-uuid"
    expires_at = datetime.now(timezone.utc)
    module = refresh_token_crud if kind == "refresh" else provider_token_crud
    factory = MagicMock(return_value=session)
    monkeypatch.setattr(module, "AsyncSession", factory)

    async def create():
        if kind == "refresh":
            return await module.create_db_refresh_token(object(), user_id, "token", expires_at)
        return await module.store_provider_token(object(), user_id, "github", "encrypted-token")

    if not valid:
        with pytest.raises(ValueError):
            asyncio.run(create())
        factory.assert_not_called()
        return

    token = asyncio.run(create())
    assert token.user_id == owner
    assert isinstance(token.user_id, uuid.UUID)
    if kind == "refresh":
        assert token.token == "token"
        assert token.expires_at == expires_at
    else:
        assert token.provider == "github"
        assert token.access_token == "encrypted-token"
        assert owner in session.exec.call_args.args[0].compile().params.values()
    session.add.assert_called_once_with(token)
    session.commit.assert_awaited_once()


def test_provider_token_update_keeps_owner_and_provider(monkeypatch, session):
    owner = uuid.uuid4()
    token = pg_models.ProviderToken(user_id=owner, provider="github", access_token="old")
    session.exec.return_value.scalar_one_or_none.return_value = token
    monkeypatch.setattr(provider_token_crud, "AsyncSession", MagicMock(return_value=session))

    updated = asyncio.run(
        provider_token_crud.store_provider_token(object(), str(owner), "github", "new")
    )

    assert updated is token
    assert token.user_id == owner
    assert token.provider == "github"
    assert token.access_token == "new"
    params = session.exec.call_args.args[0].compile().params.values()
    assert owner in params
    assert "github" in params
    session.add.assert_not_called()
    session.commit.assert_awaited_once()


@pytest.mark.parametrize("kind", ["initial", "provider", "password"])
@pytest.mark.parametrize("has_id", [True, False])
def test_user_creation_requires_flushed_identity(monkeypatch, session, kind, has_id):
    owner = uuid.uuid4() if has_id else None
    module = pg_models if kind == "initial" else user_crud
    monkeypatch.setattr(module, "AsyncSession", MagicMock(return_value=session))
    monkeypatch.setattr(user_crud, "get_user_by_provider_id", AsyncMock(return_value=None))
    monkeypatch.setattr(
        user_crud,
        "get_admin_user_creation_mode",
        lambda: admin_user_creation.AdminUserCreationMode.NONE,
    )

    async def flush():
        session.add.call_args.args[0].id = owner

    session.flush.side_effect = flush

    async def create():
        if kind == "initial":
            return (
                await pg_models.create_initial_users(
                    object(), [auth.UserPass(username="user", password="hashed")]
                )
            )[0]
        if kind == "provider":
            return await user_crud.create_user_from_provider(
                object(), user_crud.ProviderUserPayload(oauthId="123"), auth.ProviderEnum.GITHUB
            )
        return await user_crud.create_user_with_password(
            object(), "user", "user@example.com", "hashed"
        )

    if not has_id:
        with pytest.raises(ValueError, match="User ID is missing after flush"):
            asyncio.run(create())
        assert session.add.call_count == 1
        session.refresh.assert_not_awaited()
        assert session.begin.return_value.__aexit__.call_args.args[0] is ValueError
        return

    user = asyncio.run(create())
    workspace = session.add.call_args.args[0]
    assert isinstance(workspace, pg_models.Workspace)
    assert workspace.user_id == user.id == owner
    assert workspace.name == "Default"
    assert session.add.call_count == 2


@pytest.mark.parametrize("has_id", [True, False])
def test_usage_record_requires_user_identity(session, has_id):
    owner = uuid.uuid4() if has_id else None
    user = pg_models.User(id=owner, username="user", created_at=datetime.now(timezone.utc))
    operation = usage_crud._get_or_create_and_reset_record(
        session, user, pg_models.QueryTypeEnum.WEB_SEARCH, for_update=True
    )
    if not has_id:
        with pytest.raises(ValueError, match="User ID is missing"):
            asyncio.run(operation)
        session.execute.assert_not_awaited()
        session.add.assert_not_called()
        return

    record = asyncio.run(operation)
    assert record.user_id == owner
    assert record.query_type == "web_search"
    assert record.used_queries == 0
    session.add.assert_called_once_with(record)
    session.flush.assert_awaited_once()


def _graph_settings(top_k=40.0):
    return users_dto.SettingsDTO.model_construct(
        models=users_dto.ModelsSettings(defaultModel="test", excludeReasoning=False, topK=top_k)
    )


@pytest.mark.parametrize("kind", ["folder", "workspace", "graph"])
@pytest.mark.parametrize("valid", [True, False])
def test_graph_objects_parse_owner(monkeypatch, session, kind, valid):
    owner = uuid.uuid4()
    user_id = str(owner) if valid else "not-a-uuid"
    factory = MagicMock(return_value=session)
    monkeypatch.setattr(graph_crud, "AsyncSession", factory)

    async def create():
        if kind == "folder":
            return await graph_crud.create_folder(object(), user_id, "Folder")
        if kind == "workspace":
            return await graph_crud.create_workspace(object(), user_id, "Workspace")
        return await graph_crud.create_empty_graph(object(), user_id, _graph_settings(), False)

    if not valid:
        with pytest.raises(HTTPException) as exc:
            asyncio.run(create())
        assert exc.value.status_code == 400
        assert exc.value.detail == "Invalid user ID."
        factory.assert_not_called()
        return

    created = asyncio.run(create())
    assert created.user_id == owner
    assert isinstance(created.user_id, uuid.UUID)
    if kind == "graph":
        assert type(created.top_k) is int
        assert created.top_k == 40
    session.add.assert_called_once_with(created)


@pytest.mark.parametrize("kind", ["folder", "graph"])
def test_creation_still_checks_workspace_ownership(monkeypatch, session, kind):
    owner = uuid.uuid4()
    workspace_id = uuid.uuid4()
    monkeypatch.setattr(graph_crud, "AsyncSession", MagicMock(return_value=session))
    if kind == "folder":
        operation = graph_crud.create_folder(object(), str(owner), "Folder", str(workspace_id))
    else:
        operation = graph_crud.create_empty_graph(
            object(), str(owner), _graph_settings(), False, str(workspace_id)
        )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(operation)
    assert exc.value.status_code == 404
    params = session.exec.call_args.args[0].compile().params.values()
    assert owner in params
    assert workspace_id in params
    session.add.assert_not_called()


@pytest.mark.parametrize("value", [0, 1, 40, 40.0, "40"])
def test_graph_creation_converts_integral_top_k(monkeypatch, session, value):
    monkeypatch.setattr(graph_crud, "AsyncSession", MagicMock(return_value=session))
    graph = asyncio.run(
        graph_crud.create_empty_graph(object(), str(uuid.uuid4()), _graph_settings(value), False)
    )
    assert type(graph.top_k) is int
    assert graph.top_k == int(value)


@pytest.mark.parametrize("value", [40.5, "40.5", float("nan"), float("inf"), float("-inf")])
def test_graph_creation_rejects_non_integral_top_k(monkeypatch, session, value):
    factory = MagicMock(return_value=session)
    monkeypatch.setattr(graph_crud, "AsyncSession", factory)
    settings = _graph_settings(value)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(graph_crud.create_empty_graph(object(), str(uuid.uuid4()), settings, False))
    assert exc.value.status_code == 400
    assert exc.value.detail == "topK must be a finite integer."
    factory.assert_not_called()


@pytest.mark.parametrize("status", [*pg_models.PromptImproverRunStatusEnum, "invalid"])
def test_prompt_run_converts_status(monkeypatch, session, status):
    monkeypatch.setattr(prompt_improver_crud, "AsyncSession", MagicMock(return_value=session))
    operation = prompt_improver_crud.create_prompt_improver_run(
        object(),
        user_id=str(uuid.uuid4()),
        graph_id=str(uuid.uuid4()),
        node_id="node",
        parent_run_id=None,
        target_id="target",
        target_node_id=None,
        target_snapshot={},
        source_prompt="Original",
        source_template_snapshot=None,
        selected_dimension_ids=[],
        recommended_dimension_ids=[],
        audit=None,
        improved_prompt=None,
        feedback=None,
        active_phase=None,
        active_tool_call_id=None,
        clarification_tool_call_ids=[],
        status=(
            status.value if isinstance(status, pg_models.PromptImproverRunStatusEnum) else status
        ),
    )
    if status == "invalid":
        with pytest.raises(ValueError):
            asyncio.run(operation)
        session.add.assert_not_called()
        session.commit.assert_not_awaited()
        return

    run = asyncio.run(operation)
    assert run.status is status
    session.commit.assert_awaited_once()


@pytest.mark.parametrize("status", [None, "accepted", "rejected", "invalid"])
def test_prompt_changes_convert_review_status(monkeypatch, session, status):
    monkeypatch.setattr(prompt_improver_crud, "AsyncSession", MagicMock(return_value=session))
    payload = {
        "order_index": 0,
        "source_start": 0,
        "source_end": 8,
        "source_text": "Original",
        "suggested_text": "Improved",
    }
    if status is not None:
        payload["review_status"] = status
    operation = prompt_improver_crud.create_prompt_improver_changes(
        object(), run_id=str(uuid.uuid4()), changes=[payload]
    )
    if status == "invalid":
        with pytest.raises(ValueError):
            asyncio.run(operation)
        session.add.assert_not_called()
        session.commit.assert_not_awaited()
        return

    changes = asyncio.run(operation)
    assert changes[0].review_status is pg_models.PromptImproverChangeStatusEnum(
        status or "accepted"
    )
    session.commit.assert_awaited_once()
