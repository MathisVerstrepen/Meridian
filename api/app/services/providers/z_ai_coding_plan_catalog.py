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

Z_AI_CODING_PLAN_PROVIDER_KEY = "z_ai_coding_plan.api_key"
Z_AI_CODING_PLAN_MODEL_PREFIX = "z-ai-plan/"
Z_AI_CODING_PLAN_LABEL = "Z.AI Coding Plan"
Z_AI_CODING_PLAN_SUPPORTED_TOOL_NAMES = list(MERIDIAN_SUPPORTED_TOOL_NAMES)


def _normalize_input_modalities(input_modalities: Any) -> list[str]:
    if not isinstance(input_modalities, list):
        return ["text"]
    normalized = [str(modality).strip().lower() for modality in input_modalities if modality]
    return normalized or ["text"]


def _get_models_dev_input_modalities(payload: dict[str, Any]) -> Any:
    modalities = payload.get("modalities")
    if isinstance(modalities, dict):
        return modalities.get("input")
    return None


def _get_models_dev_output_modalities(payload: dict[str, Any]) -> list[str]:
    modalities = payload.get("modalities")
    if isinstance(modalities, dict):
        output_modalities = modalities.get("output")
        if isinstance(output_modalities, list):
            normalized = [
                str(modality).strip().lower() for modality in output_modalities if modality
            ]
            if normalized:
                return normalized
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
    input_description = "+".join(input_modalities)
    output_description = "+".join(output_modalities)
    return f"{input_description}->{output_description}"


def normalize_z_ai_coding_plan_model(payload: Any) -> ModelInfo | None:
    if not isinstance(payload, dict):
        return None

    model_id = str(payload.get("model") or payload.get("id") or "").strip()
    if not model_id:
        return None

    display_name = str(payload.get("name") or model_id).strip()
    input_modalities = _normalize_input_modalities(_get_models_dev_input_modalities(payload))
    output_modalities = _get_models_dev_output_modalities(payload)
    return ModelInfo(
        id=f"{Z_AI_CODING_PLAN_MODEL_PREFIX}{model_id}",
        name=display_name,
        icon="z-ai",
        architecture=Architecture(
            input_modalities=input_modalities,
            modality=_build_modality_description(input_modalities, output_modalities),
            output_modalities=output_modalities,
            tokenizer="glm",
        ),
        context_length=_get_context_length(payload),
        created=payload.get("release_date") or payload.get("created"),
        pricing=_get_pricing(payload),
        provider=InferenceProviderEnum.Z_AI_CODING_PLAN,
        billingType=BillingTypeEnum.SUBSCRIPTION,
        requiresConnection=True,
        supportsStructuredOutputs=False,
        supportsMeridianTools=True,
        supportedMeridianToolNames=list(Z_AI_CODING_PLAN_SUPPORTED_TOOL_NAMES),
        toolsSupport=True,
    )


def build_z_ai_coding_plan_models_from_models_dev(payload: Any) -> list[ModelInfo]:
    models_payload = get_models_dev_provider_models(payload, "zai-coding-plan")
    if not models_payload:
        return []

    normalized_models: list[ModelInfo] = []
    seen_model_ids: set[str] = set()
    for model_id, raw_model in models_payload.items():
        if not isinstance(raw_model, dict):
            continue
        normalized_model = normalize_z_ai_coding_plan_model({"id": model_id, **raw_model})
        if normalized_model is None or normalized_model.id in seen_model_ids:
            continue
        if normalized_model.architecture.input_modalities != ["text"]:
            continue
        seen_model_ids.add(normalized_model.id)
        normalized_models.append(normalized_model)

    normalized_models.sort(key=lambda model: (model.created or "", model.id), reverse=True)
    if normalized_models:
        return normalized_models
    return []


async def get_z_ai_coding_plan_models(models_dev_catalog: Any | None = None) -> list[ModelInfo]:
    if models_dev_catalog is None:
        return []
    return build_z_ai_coding_plan_models_from_models_dev(models_dev_catalog)
