from typing import Any

from models.inference import (
    Architecture,
    BillingTypeEnum,
    InferenceProviderEnum,
    ModelInfo,
    Pricing,
)
from services.providers.common import MERIDIAN_SUPPORTED_TOOL_NAMES
from services.providers.models_dev import get_models_dev_provider_models

OPENCODE_GO_PROVIDER_KEY = "opencode_go.api_key"
OPENCODE_GO_MODEL_PREFIX = "opencode-go/"
OPENCODE_GO_MODELS_DEV_PROVIDER_KEY = "opencode-go"
OPENCODE_GO_LABEL = "OpenCode Go"
OPENCODE_GO_SUPPORTED_TOOL_NAMES = list(MERIDIAN_SUPPORTED_TOOL_NAMES)

# models.dev exposes `temperature: false` for this model, but the API expects
# fixed sampling values instead of omitted sampling fields.
OPENCODE_GO_TEMPERATURE_OVERRIDES = {"kimi-k2.7-code": 1.0}
OPENCODE_GO_TOP_P_OVERRIDES = {"kimi-k2.7-code": 0.95}


def _normalize_modalities(modalities: Any) -> list[str]:
    if not isinstance(modalities, list):
        return ["text"]
    normalized = [str(modality).strip().lower() for modality in modalities if modality]
    return normalized or ["text"]


def _get_models_dev_input_modalities(payload: dict[str, Any]) -> Any:
    modalities = payload.get("modalities")
    if isinstance(modalities, dict):
        return modalities.get("input")
    return None


def _get_models_dev_output_modalities(payload: dict[str, Any]) -> list[str]:
    modalities = payload.get("modalities")
    if isinstance(modalities, dict):
        return _normalize_modalities(modalities.get("output"))
    return ["text"]


def _get_context_length(payload: dict[str, Any]) -> int:
    context_length = payload.get("contextLength")
    if isinstance(context_length, int):
        return context_length

    limit = payload.get("limit")
    if isinstance(limit, dict) and isinstance(limit.get("context"), int):
        return int(limit["context"])
    return -1


def _get_pricing(payload: dict[str, Any]) -> Pricing:
    cost = payload.get("cost")
    if isinstance(cost, dict):
        prompt = cost.get("input")
        completion = cost.get("output")
        return Pricing(prompt=str(prompt or "0"), completion=str(completion or "0"))
    return Pricing(prompt="0", completion="0")


def _build_modality_description(input_modalities: list[str], output_modalities: list[str]) -> str:
    return f"{'+'.join(input_modalities)}->{'+'.join(output_modalities)}"


def normalize_opencode_go_model(payload: Any) -> ModelInfo | None:
    if not isinstance(payload, dict):
        return None

    model_id = str(payload.get("model") or payload.get("id") or "").strip()
    if not model_id:
        return None

    display_name = str(payload.get("name") or model_id).strip()
    input_modalities = _normalize_modalities(_get_models_dev_input_modalities(payload))
    output_modalities = _get_models_dev_output_modalities(payload)
    return ModelInfo(
        id=f"{OPENCODE_GO_MODEL_PREFIX}{model_id}",
        name=display_name,
        icon="opencode",
        architecture=Architecture(
            input_modalities=input_modalities,
            modality=_build_modality_description(input_modalities, output_modalities),
            output_modalities=output_modalities,
            tokenizer="opencode",
        ),
        context_length=_get_context_length(payload),
        created=payload.get("release_date") or payload.get("created"),
        pricing=_get_pricing(payload),
        provider=InferenceProviderEnum.OPENCODE_GO,
        billingType=BillingTypeEnum.SUBSCRIPTION,
        requiresConnection=True,
        supportsStructuredOutputs=False,
        supportsMeridianTools=True,
        supportedMeridianToolNames=list(OPENCODE_GO_SUPPORTED_TOOL_NAMES),
        toolsSupport=True,
    )


def build_opencode_go_models_from_models_dev(payload: Any) -> list[ModelInfo]:
    models_payload = get_models_dev_provider_models(payload, OPENCODE_GO_MODELS_DEV_PROVIDER_KEY)
    if not models_payload:
        return []

    normalized_models: list[ModelInfo] = []
    seen_model_ids: set[str] = set()
    for model_id, raw_model in models_payload.items():
        if not isinstance(raw_model, dict):
            continue
        normalized_model = normalize_opencode_go_model({"id": model_id, **raw_model})
        if normalized_model is None or normalized_model.id in seen_model_ids:
            continue
        seen_model_ids.add(normalized_model.id)
        normalized_models.append(normalized_model)

    normalized_models.sort(key=lambda model: (model.created or "", model.id), reverse=True)
    return normalized_models


async def get_opencode_go_models(models_dev_catalog: Any | None = None) -> list[ModelInfo]:
    if models_dev_catalog is None:
        return []
    return build_opencode_go_models_from_models_dev(models_dev_catalog)
