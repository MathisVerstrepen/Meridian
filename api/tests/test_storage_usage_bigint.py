import importlib
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

import sqlalchemy as sa

APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.append(str(APP_DIR))

UserStorageUsage = importlib.import_module("database.pg.models").UserStorageUsage
migration = importlib.import_module(
    "migrations.versions.4e7a9c2b6d10_widen_storage_usage_to_bigint"
)


def test_storage_usage_model_uses_bigint() -> None:
    column = UserStorageUsage.__table__.c.total_bytes_used

    assert isinstance(column.type, sa.BigInteger)
    assert column.nullable is False

    usage = UserStorageUsage(user_id=uuid.uuid4(), total_bytes_used=2_152_137_593)
    assert usage.total_bytes_used == 2_152_137_593


def test_storage_usage_migration_upgrades_integer_to_bigint() -> None:
    with patch.object(migration.op, "alter_column") as alter_column:
        migration.upgrade()

    alter_column.assert_called_once()
    args, kwargs = alter_column.call_args
    assert args == ("user_storage_usage", "total_bytes_used")
    assert isinstance(kwargs["existing_type"], sa.Integer)
    assert isinstance(kwargs["type_"], sa.BigInteger)
    assert kwargs["existing_nullable"] is False


def test_storage_usage_migration_downgrades_bigint_to_integer() -> None:
    with patch.object(migration.op, "alter_column") as alter_column:
        migration.downgrade()

    alter_column.assert_called_once()
    args, kwargs = alter_column.call_args
    assert args == ("user_storage_usage", "total_bytes_used")
    assert isinstance(kwargs["existing_type"], sa.BigInteger)
    assert isinstance(kwargs["type_"], sa.Integer)
    assert kwargs["existing_nullable"] is False
