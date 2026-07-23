import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from const.settings import DEFAULT_SETTINGS
from models.message import NodeTypeEnum
from models.usersDTO import BlockSettings, SettingsDTO
from services import settings as settings_service


EXPECTED_WHEELS = {
    "contextInputWheel": [
        {"name": "Slot 1", "mainBloc": "textToText", "options": ["prompt"]},
        {"name": "Slot 2", "mainBloc": "routing", "options": ["prompt"]},
        {"name": "Slot 3", "mainBloc": "parallelization", "options": ["prompt"]},
        {"name": "Slot 4", "mainBloc": None, "options": []},
    ],
    "contextWheel": [
        {"name": "Slot 1", "mainBloc": "textToText", "options": ["prompt"]},
        {"name": "Slot 2", "mainBloc": "routing", "options": ["prompt"]},
        {"name": "Slot 3", "mainBloc": "parallelization", "options": ["prompt"]},
        {"name": "Slot 4", "mainBloc": None, "options": []},
    ],
    "promptInputWheel": [
        {"name": "Slot 1", "mainBloc": "prompt", "options": []},
        {"name": "Slot 2", "mainBloc": None, "options": []},
        {"name": "Slot 3", "mainBloc": None, "options": []},
        {"name": "Slot 4", "mainBloc": None, "options": []},
    ],
    "promptOutputWheel": [
        {"name": "Slot 1", "mainBloc": "textToText", "options": []},
        {"name": "Slot 2", "mainBloc": "routing", "options": []},
        {"name": "Slot 3", "mainBloc": "parallelization", "options": []},
        {"name": "Slot 4", "mainBloc": None, "options": []},
    ],
    "attachmentInputWheel": [
        {"name": "Slot 1", "mainBloc": "filePrompt", "options": []},
        {"name": "Slot 2", "mainBloc": "github", "options": []},
        {"name": "Slot 3", "mainBloc": None, "options": []},
        {"name": "Slot 4", "mainBloc": None, "options": []},
    ],
    "attachmentOutputWheel": [
        {"name": "Slot 1", "mainBloc": "textToText", "options": ["prompt"]},
        {"name": "Slot 2", "mainBloc": "routing", "options": ["prompt"]},
        {"name": "Slot 3", "mainBloc": "parallelization", "options": ["prompt"]},
        {"name": "Slot 4", "mainBloc": None, "options": []},
    ],
}

CUSTOM_CONTEXT_WHEEL = [
    {"name": "Custom 1", "mainBloc": "routing", "options": ["github"]},
    {"name": "Custom 2", "mainBloc": None, "options": []},
]

NEW_WHEEL_KEYS = {
    "contextInputWheel",
    "promptInputWheel",
    "promptOutputWheel",
    "attachmentInputWheel",
    "attachmentOutputWheel",
}


def _legacy_settings_payload() -> dict:
    payload = DEFAULT_SETTINGS.model_dump(mode="json")
    payload["block"]["contextWheel"] = CUSTOM_CONTEXT_WHEEL
    for key in NEW_WHEEL_KEYS:
        payload["block"].pop(key)
    return payload


def test_block_settings_and_canonical_defaults_expose_exact_six_wheels():
    assert BlockSettings().model_dump(mode="json") == EXPECTED_WHEELS
    assert DEFAULT_SETTINGS.block.model_dump(mode="json") == EXPECTED_WHEELS


def test_block_settings_wheel_defaults_are_independent():
    first = BlockSettings()
    second = BlockSettings()

    first.contextInputWheel[0].name = "Changed"
    first.contextInputWheel[0].options.append(NodeTypeEnum.GITHUB)
    first.promptInputWheel.append(first.promptInputWheel[0].model_copy(deep=True))

    assert first.contextWheel[0].name == "Slot 1"
    assert first.contextWheel[0].options == [NodeTypeEnum.PROMPT]
    assert second.contextInputWheel[0].name == "Slot 1"
    assert second.contextInputWheel[0].options == [NodeTypeEnum.PROMPT]
    assert len(second.promptInputWheel) == 4


def test_legacy_payload_hydrates_new_wheels_and_preserves_context_wheel():
    settings = SettingsDTO.model_validate(_legacy_settings_payload())
    block = settings.block.model_dump(mode="json")

    assert block["contextWheel"] == CUSTOM_CONTEXT_WHEEL
    for key in NEW_WHEEL_KEYS:
        assert block[key] == EXPECTED_WHEELS[key]


def test_canonical_settings_round_trip_preserves_all_wheels():
    dumped = DEFAULT_SETTINGS.model_dump(mode="json")
    round_tripped = SettingsDTO.model_validate(dumped).model_dump(mode="json")

    assert round_tripped["block"] == EXPECTED_WHEELS


def test_get_user_settings_hydrates_stored_legacy_payload(monkeypatch):
    legacy_payload = _legacy_settings_payload()

    async def fake_get_settings(pg_engine, user_id):
        assert pg_engine is fake_engine
        assert user_id == "legacy-user"
        return legacy_payload

    fake_engine = object()
    monkeypatch.setattr(settings_service, "get_settings", fake_get_settings)

    settings = asyncio.run(settings_service.get_user_settings(fake_engine, "legacy-user"))
    block = settings.block.model_dump(mode="json")

    assert block["contextWheel"] == CUSTOM_CONTEXT_WHEEL
    for key in NEW_WHEEL_KEYS:
        assert block[key] == EXPECTED_WHEELS[key]
