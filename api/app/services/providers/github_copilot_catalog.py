from typing import Any

from models.inference import (
    Architecture,
    BillingTypeEnum,
    InferenceProviderEnum,
    ModelInfo,
    Pricing,
)
from services.providers.common import MERIDIAN_SUPPORTED_TOOL_NAMES

GITHUB_COPILOT_PROVIDER_KEY = "github_copilot.github_token"
GITHUB_COPILOT_MODEL_PREFIX = "github-copilot/"
GITHUB_COPILOT_LABEL = "GitHub Copilot"
GITHUB_COPILOT_SUPPORTED_TOOL_NAMES = list(MERIDIAN_SUPPORTED_TOOL_NAMES)


def _normalize_model_alias(model_id: object | None) -> str:
    normalized_model_id = str(model_id or "").strip()
    if normalized_model_id.startswith(GITHUB_COPILOT_MODEL_PREFIX):
        return normalized_model_id[len(GITHUB_COPILOT_MODEL_PREFIX) :]
    return normalized_model_id


def build_github_copilot_model(
    *,
    model_id: str,
    name: str,
    supports_vision: bool,
    context_length: int | None = None,
) -> ModelInfo:
    return ModelInfo(
        id=f"{GITHUB_COPILOT_MODEL_PREFIX}{model_id}",
        name=name,
        icon="github",
        architecture=Architecture(
            # Meridian currently rejects Copilot image inputs at request validation time.
            input_modalities=["text"],
            modality="text->text",
            output_modalities=["text"],
            tokenizer="copilot",
        ),
        context_length=context_length,
        pricing=Pricing(prompt="0", completion="0"),
        provider=InferenceProviderEnum.GITHUB_COPILOT,
        billingType=BillingTypeEnum.SUBSCRIPTION,
        requiresConnection=True,
        supportsStructuredOutputs=False,
        supportsMeridianTools=True,
        supportedMeridianToolNames=GITHUB_COPILOT_SUPPORTED_TOOL_NAMES,
        toolsSupport=True,
    )


def normalize_github_copilot_model(raw_model: Any) -> ModelInfo | None:
    raw_id = _normalize_model_alias(getattr(raw_model, "id", None))
    if not raw_id:
        return None

    capabilities = getattr(raw_model, "capabilities", None)
    supports = getattr(capabilities, "supports", None)
    limits = getattr(capabilities, "limits", None)
    supports_vision = bool(getattr(supports, "vision", False))

    return build_github_copilot_model(
        model_id=raw_id,
        name=str(getattr(raw_model, "name", None) or raw_id),
        supports_vision=supports_vision,
        context_length=getattr(limits, "max_context_window_tokens", None),
    )
