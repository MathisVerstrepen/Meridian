import importlib.util
import sys
from pathlib import Path
from types import ModuleType

API_DIR = Path(__file__).resolve().parents[1]
APP_DIR = API_DIR / "app"
sys.path.append(str(APP_DIR))

from services.rate_limit import build_redis_storage_uri  # noqa: E402


def load_rate_limit_module(module_name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, APP_DIR / "services/rate_limit.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_redis_storage_uri_without_password():
    assert build_redis_storage_uri("redis", 6379, None) == "redis://redis:6379"


def test_build_redis_storage_uri_encodes_password():
    storage_uri = build_redis_storage_uri("redis", 6380, "p@ss:/?#% word")

    assert storage_uri == "redis://:p%40ss%3A%2F%3F%23%25%20word@redis:6380"
    assert "p@ss:/?#% word" not in storage_uri


def test_limiter_uses_environment_available_before_import(monkeypatch):
    monkeypatch.setenv("REDIS_HOST", "configured-redis")
    monkeypatch.setenv("REDIS_PORT", "6381")
    monkeypatch.setenv("REDIS_PASSWORD", "configured/password")

    rate_limit = load_rate_limit_module("rate_limit_with_configured_environment")

    assert rate_limit.limiter._storage_uri == (
        "redis://:configured%2Fpassword@configured-redis:6381"
    )


def test_host_development_loads_env_file_before_application_import():
    run_dev_script = (API_DIR / "run-dev.sh").read_text()
    env_file_option = '--env-file "${SCRIPT_DIR}/../docker/env/.env.local"'

    assert env_file_option in run_dev_script
    assert run_dev_script.index(env_file_option) < run_dev_script.index("main:app")
