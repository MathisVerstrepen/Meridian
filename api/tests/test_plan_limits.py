import copy
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from const.plans import (  # noqa: E402
    MIB_IN_BYTES,
    PLAN_LIMITS,
    configure_plan_limits,
    load_plan_limits,
)
from database.pg.models import QueryTypeEnum  # noqa: E402
from database.pg.user_ops import storage_crud, usage_crud  # noqa: E402
from fastapi import HTTPException  # noqa: E402

PLAN_ENV_DEFAULTS = {
    "PLAN_FREE_WEB_SEARCH_LIMIT": 0,
    "PLAN_FREE_LINK_EXTRACTION_LIMIT": 0,
    "PLAN_FREE_STORAGE_LIMIT_MIB": 50,
    "PLAN_PREMIUM_WEB_SEARCH_LIMIT": 200,
    "PLAN_PREMIUM_LINK_EXTRACTION_LIMIT": 1000,
    "PLAN_PREMIUM_STORAGE_LIMIT_MIB": 5120,
}

EXPECTED_DEFAULTS = {
    "free": {
        "web_search": 0,
        "link_extraction": 0,
        "storage": 50 * MIB_IN_BYTES,
    },
    "premium": {
        "web_search": 200,
        "link_extraction": 1000,
        "storage": 5120 * MIB_IN_BYTES,
    },
}


@pytest.fixture(autouse=True)
def restore_plan_limits():
    original_limits = copy.deepcopy(PLAN_LIMITS)
    yield
    PLAN_LIMITS.clear()
    PLAN_LIMITS.update(original_limits)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_load_plan_limits_uses_historical_defaults():
    assert load_plan_limits(lambda _field: None) == EXPECTED_DEFAULTS


def test_load_plan_limits_wires_all_overrides_and_converts_mib():
    values = {
        "PLAN_FREE_WEB_SEARCH_LIMIT": " 11 ",
        "PLAN_FREE_LINK_EXTRACTION_LIMIT": "12",
        "PLAN_FREE_STORAGE_LIMIT_MIB": "13",
        "PLAN_PREMIUM_WEB_SEARCH_LIMIT": "21",
        "PLAN_PREMIUM_LINK_EXTRACTION_LIMIT": "22",
        "PLAN_PREMIUM_STORAGE_LIMIT_MIB": "23",
    }

    assert load_plan_limits(values.get) == {
        "free": {
            "web_search": 11,
            "link_extraction": 12,
            "storage": 13 * MIB_IN_BYTES,
        },
        "premium": {
            "web_search": 21,
            "link_extraction": 22,
            "storage": 23 * MIB_IN_BYTES,
        },
    }


def test_load_plan_limits_accepts_zero_for_every_field():
    values = {field: "0" for field in PLAN_ENV_DEFAULTS}

    assert load_plan_limits(values.get) == {
        "free": {"web_search": 0, "link_extraction": 0, "storage": 0},
        "premium": {"web_search": 0, "link_extraction": 0, "storage": 0},
    }


@pytest.mark.parametrize("field", PLAN_ENV_DEFAULTS)
@pytest.mark.parametrize("invalid_value", ["", " ", "-1", "true", "3.5", "1e3"])
def test_load_plan_limits_rejects_each_invalid_explicit_value(field, invalid_value):
    values = {field: invalid_value}

    with pytest.raises(ValueError, match=field):
        load_plan_limits(values.get)


def test_configure_plan_limits_preserves_identity_and_is_atomic_on_error():
    plan_limits_reference = PLAN_LIMITS
    configured_values = {field: str(index) for index, field in enumerate(PLAN_ENV_DEFAULTS, 1)}
    configure_plan_limits(configured_values.get)
    configured_snapshot = copy.deepcopy(PLAN_LIMITS)

    with pytest.raises(ValueError, match="PLAN_PREMIUM_STORAGE_LIMIT_MIB"):
        configure_plan_limits(
            {
                **configured_values,
                "PLAN_PREMIUM_STORAGE_LIMIT_MIB": "invalid",
            }.get
        )

    assert PLAN_LIMITS is plan_limits_reference
    assert PLAN_LIMITS == configured_snapshot


class _AsyncContext:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _QuerySession:
    def __init__(self, user):
        self.user = user
        self.added = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    def begin(self):
        return _AsyncContext()

    async def get(self, _model, _user_id):
        return self.user

    def add(self, record):
        self.added.append(record)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("query_type", "env_field", "configured_limit"),
    [
        (QueryTypeEnum.WEB_SEARCH, "PLAN_FREE_WEB_SEARCH_LIMIT", 2),
        (QueryTypeEnum.LINK_EXTRACTION, "PLAN_FREE_LINK_EXTRACTION_LIMIT", 3),
    ],
)
async def test_configured_query_limits_enforce_existing_boundary(
    monkeypatch, query_type, env_field, configured_limit
):
    configure_plan_limits({env_field: str(configured_limit)}.get)
    user_id = uuid.uuid4()
    user = SimpleNamespace(id=user_id, plan_type="free")
    usage_record = SimpleNamespace(used_queries=configured_limit - 1)
    session = _QuerySession(user)

    async def get_usage_record(_session, _user, requested_type, for_update=False):
        assert requested_type == query_type
        assert for_update is True
        return usage_record

    monkeypatch.setattr(usage_crud, "AsyncSession", lambda _engine: session)
    monkeypatch.setattr(usage_crud, "_get_or_create_and_reset_record", get_usage_record)

    await usage_crud.check_and_increment_query_usage(object(), str(user_id), query_type)
    assert usage_record.used_queries == configured_limit

    with pytest.raises(HTTPException) as exc_info:
        await usage_crud.check_and_increment_query_usage(object(), str(user_id), query_type)

    assert exc_info.value.status_code == 429
    assert usage_record.used_queries == configured_limit


class _StorageResult:
    def __init__(self, record):
        self.record = record

    def scalar_one_or_none(self):
        return self.record


class _StorageSession(_QuerySession):
    def __init__(self, user, record):
        super().__init__(user)
        self.record = record

    async def exec(self, _statement):
        return _StorageResult(self.record)


@pytest.mark.anyio
async def test_configured_storage_limit_allows_exact_boundary_and_rejects_excess(monkeypatch):
    configure_plan_limits({"PLAN_FREE_STORAGE_LIMIT_MIB": "1"}.get)
    user_id = uuid.uuid4()
    record = SimpleNamespace(total_bytes_used=MIB_IN_BYTES - 1)
    session = _StorageSession(SimpleNamespace(plan_type="free"), record)
    monkeypatch.setattr(storage_crud, "AsyncSession", lambda _engine: session)

    await storage_crud.check_and_reserve_storage(object(), user_id, 1)
    assert record.total_bytes_used == MIB_IN_BYTES

    with pytest.raises(HTTPException) as exc_info:
        await storage_crud.check_and_reserve_storage(object(), user_id, 1)

    assert exc_info.value.status_code == 403
    assert record.total_bytes_used == MIB_IN_BYTES


@pytest.mark.anyio
async def test_configured_limits_are_used_in_query_and_storage_reporting(monkeypatch):
    configure_plan_limits(
        {
            "PLAN_PREMIUM_WEB_SEARCH_LIMIT": "7",
            "PLAN_PREMIUM_STORAGE_LIMIT_MIB": "1",
        }.get
    )
    user = SimpleNamespace(id=uuid.uuid4(), plan_type="premium")
    now = datetime.now(timezone.utc)
    usage_record = SimpleNamespace(
        used_queries=4,
        billing_period_start=now,
        billing_period_end=now,
    )
    query_session = _QuerySession(user)

    async def get_usage_record(_session, _user, _query_type, for_update=False):
        assert for_update is False
        return usage_record

    async def commit():
        return None

    query_session.commit = commit
    monkeypatch.setattr(usage_crud, "AsyncSession", lambda _engine: query_session)
    monkeypatch.setattr(usage_crud, "_get_or_create_and_reset_record", get_usage_record)

    query_usage = await usage_crud.get_usage_record(object(), user, QueryTypeEnum.WEB_SEARCH)
    assert query_usage.limit == 7

    storage_record = SimpleNamespace(total_bytes_used=2 * MIB_IN_BYTES)
    storage_session = _StorageSession(user, storage_record)

    async def calculate_breakdown(_session, _user_id):
        return storage_record.total_bytes_used, []

    monkeypatch.setattr(storage_crud, "AsyncSession", lambda _engine: storage_session)
    monkeypatch.setattr(storage_crud, "_calculate_storage_breakdown", calculate_breakdown)

    storage_usage = await storage_crud.get_storage_usage(object(), user)
    assert storage_usage.limit_bytes == MIB_IN_BYTES
    assert storage_usage.percentage == 100.0
