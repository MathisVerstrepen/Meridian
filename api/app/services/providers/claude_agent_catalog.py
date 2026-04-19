import hashlib
import logging
import time
from collections.abc import Awaitable, Callable

from models.inference import (
    Architecture,
    BillingTypeEnum,
    InferenceProviderEnum,
    ModelInfo,
    Pricing,
)
from services.providers.common import MERIDIAN_SUPPORTED_TOOL_NAMES

logger = logging.getLogger("uvicorn.error")

# Maintenance note for future agents:
# This catalog intentionally stays static because the Claude Agent / Claude Code
# subscription token path does not expose a documented "list my available Claude
# Code aliases" endpoint. When updating these aliases, verify them against the
# official Anthropic docs first:
# - Claude Code model aliases:
#   https://docs.anthropic.com/en/docs/claude-code/model-config
# - Anthropic Models API overview (API-key based, not Claude Code subscription discovery):
#   https://platform.claude.com/docs/en/api/models/list
# Keep this list limited to documented Claude Code aliases Meridian actually
# supports. Do not infer new aliases from model marketing pages alone.

CLAUDE_AGENT_PROVIDER_KEY = "claude_agent.oauth_token"
CLAUDE_AGENT_MODEL_PREFIX = "claude-agent/"
CLAUDE_AGENT_LABEL = "Claude Agent"
CLAUDE_AGENT_SUPPORTED_TOOL_NAMES = list(MERIDIAN_SUPPORTED_TOOL_NAMES)
CLAUDE_AGENT_ALIAS_CACHE_TTL_SECONDS = 60 * 60
CLAUDE_AGENT_MODEL_DEFINITIONS = [
    ("default", "Claude Agent Default"),
    ("sonnet", "Claude Agent Sonnet"),
    ("opus", "Claude Agent Opus"),
    ("haiku", "Claude Agent Haiku"),
]

_validated_alias_cache: dict[str, tuple[float, tuple[str, ...]]] = {}


def _build_claude_agent_model(alias: str, display_name: str) -> ModelInfo:
    return ModelInfo(
        id=f"{CLAUDE_AGENT_MODEL_PREFIX}{alias}",
        name=display_name,
        icon="anthropic",
        architecture=Architecture(
            input_modalities=["text"],
            modality="text->text",
            output_modalities=["text"],
            tokenizer="claude",
        ),
        context_length=200000,
        pricing=Pricing(prompt="0", completion="0"),
        provider=InferenceProviderEnum.CLAUDE_AGENT,
        billingType=BillingTypeEnum.SUBSCRIPTION,
        requiresConnection=True,
        supportsStructuredOutputs=False,
        supportsMeridianTools=True,
        supportedMeridianToolNames=CLAUDE_AGENT_SUPPORTED_TOOL_NAMES,
        toolsSupport=True,
    )


CLAUDE_AGENT_MODELS = [
    _build_claude_agent_model(alias, display_name)
    for alias, display_name in CLAUDE_AGENT_MODEL_DEFINITIONS
]


def _copy_models(models: list[ModelInfo]) -> list[ModelInfo]:
    return [model.model_copy(deep=True) for model in models]


def _get_cache_key(oauth_token: str) -> str:
    return hashlib.sha256(oauth_token.encode("utf-8")).hexdigest()


def _get_cached_aliases(oauth_token: str) -> tuple[str, ...] | None:
    cache_key = _get_cache_key(oauth_token)
    cached_entry = _validated_alias_cache.get(cache_key)
    if cached_entry is None:
        return None

    validated_at, model_ids = cached_entry
    if time.monotonic() - validated_at > CLAUDE_AGENT_ALIAS_CACHE_TTL_SECONDS:
        _validated_alias_cache.pop(cache_key, None)
        return None
    return model_ids


def _set_cached_aliases(oauth_token: str, model_ids: tuple[str, ...]) -> None:
    _validated_alias_cache[_get_cache_key(oauth_token)] = (time.monotonic(), model_ids)


async def get_claude_agent_models(
    *,
    oauth_token: str | None = None,
    validate_aliases: bool = False,
    alias_validator: Callable[[str, str], Awaitable[bool]] | None = None,
) -> list[ModelInfo]:
    if not oauth_token or not validate_aliases or alias_validator is None:
        return _copy_models(CLAUDE_AGENT_MODELS)

    cached_model_ids = _get_cached_aliases(oauth_token)
    if cached_model_ids is not None:
        return _copy_models(
            [model for model in CLAUDE_AGENT_MODELS if model.id in cached_model_ids]
        )

    validated_models: list[ModelInfo] = []
    for model in CLAUDE_AGENT_MODELS:
        try:
            if await alias_validator(oauth_token, model.id):
                validated_models.append(model)
        except Exception:
            logger.warning(
                "Failed to validate Claude Agent model alias %s",
                model.id,
                exc_info=True,
            )

    if not validated_models:
        logger.warning(
            "Claude Agent alias validation returned no available models; "
            "falling back to static catalog."
        )
        return _copy_models(CLAUDE_AGENT_MODELS)

    _set_cached_aliases(oauth_token, tuple(model.id for model in validated_models))
    return _copy_models(validated_models)
