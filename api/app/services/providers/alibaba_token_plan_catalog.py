import json
import re
from typing import Any

import httpx
from models.inference import (
    Architecture,
    BillingTypeEnum,
    InferenceProviderEnum,
    ModelInfo,
    Pricing,
)
from services.providers.common import MERIDIAN_SUPPORTED_TOOL_NAMES
from services.providers.models_dev import get_models_dev_provider_models

ALIBABA_TOKEN_PLAN_PROVIDER_KEY = "alibaba_token_plan.api_key"
ALIBABA_TOKEN_PLAN_MODEL_PREFIX = "alibaba-token-plan/"
ALIBABA_TOKEN_PLAN_MODELS_DEV_PROVIDER_KEY = "alibaba-token-plan"
ALIBABA_TOKEN_PLAN_LABEL = "Alibaba Cloud Token Plan (Personal)"
ALIBABA_TOKEN_PLAN_SUPPORTED_TOOL_NAMES = list(MERIDIAN_SUPPORTED_TOOL_NAMES)
ALIBABA_TOKEN_PLAN_MODELS_URL = (
    "https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1/models"
)

MAX_CATALOG_BYTES = 2 * 1024 * 1024
MAX_CATALOG_ENTRIES = 5_000
MAX_MODEL_ID_LENGTH = 255 - len(ALIBABA_TOKEN_PLAN_MODEL_PREFIX)
_MODEL_ID_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_HAPPYHORSE_OPERATION_TOKENS = frozenset({"t2v", "i2v", "r2v"})

_PRESENTATION_BY_FAMILY = (
    ("qwen", "qwen", "qwen"),
    ("glm", "z-ai", "glm"),
    ("deepseek", "deepseek", "deepseek"),
    ("kimi", "moonshotai", "kimi"),
    ("minimax", "minimax", "minimax"),
)


class AlibabaTokenPlanCatalogError(RuntimeError):
    """A sanitized live-catalog discovery failure."""


def classify_happyhorse_operation(model_id: str) -> str | None:
    raw_model_id = model_id
    if raw_model_id.startswith(ALIBABA_TOKEN_PLAN_MODEL_PREFIX):
        raw_model_id = raw_model_id[len(ALIBABA_TOKEN_PLAN_MODEL_PREFIX) :]
    tokens = [token for token in re.split(r"[^a-z0-9]+", raw_model_id.casefold()) if token]
    if "happyhorse" not in tokens:
        return None
    operations = {token for token in tokens if token in _HAPPYHORSE_OPERATION_TOKENS}
    if len(operations) != 1:
        return None
    return next(iter(operations))


def _normalize_modalities(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    normalized: list[str] = []
    for modality in value:
        if not isinstance(modality, str):
            continue
        normalized_modality = modality.strip().lower()
        if normalized_modality and normalized_modality not in normalized:
            normalized.append(normalized_modality)
    return normalized or None


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
    if not isinstance(cost, dict):
        return Pricing(prompt="0", completion="0")
    return Pricing(
        prompt=str(cost.get("input") or "0"),
        completion=str(cost.get("output") or "0"),
        image=str(cost["image"]) if cost.get("image") is not None else None,
        video=str(cost["video"]) if cost.get("video") is not None else None,
    )


def _get_family_metadata(payload: dict[str, Any]) -> str:
    family = payload.get("family")
    if isinstance(family, str):
        return family.strip()
    if isinstance(family, dict):
        for key in ("id", "name"):
            value = family.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _get_presentation(
    payload: dict[str, Any], model_id: str, display_name: str
) -> tuple[str | None, str]:
    for candidate in (_get_family_metadata(payload), model_id, display_name):
        normalized_candidate = candidate.strip().casefold()
        for prefix, icon, tokenizer in _PRESENTATION_BY_FAMILY:
            if normalized_candidate.startswith(prefix):
                return icon, tokenizer
    return None, "unknown"


def normalize_alibaba_token_plan_model(payload: Any) -> ModelInfo | None:
    if not isinstance(payload, dict):
        return None
    model_id = str(payload.get("model") or payload.get("id") or "").strip()
    if not model_id:
        return None
    modalities = payload.get("modalities")
    if not isinstance(modalities, dict):
        return None
    input_modalities = _normalize_modalities(modalities.get("input"))
    output_modalities = _normalize_modalities(modalities.get("output"))
    if (
        input_modalities is None
        or output_modalities is None
        or "text" not in input_modalities
        or not ({"text", "image"} & set(output_modalities))
    ):
        return None
    output_modalities = [item for item in output_modalities if item in {"text", "image"}]
    display_name = str(payload.get("name") or model_id).strip() or model_id
    icon, tokenizer = _get_presentation(payload, model_id, display_name)
    supports_tools = "text" in output_modalities
    return ModelInfo(
        id=f"{ALIBABA_TOKEN_PLAN_MODEL_PREFIX}{model_id}",
        name=display_name,
        icon=icon,
        architecture=Architecture(
            input_modalities=input_modalities,
            modality=f"{'+'.join(input_modalities)}->{'+'.join(output_modalities)}",
            output_modalities=output_modalities,
            tokenizer=tokenizer,
        ),
        context_length=_get_context_length(payload),
        created=payload.get("release_date") or payload.get("created"),
        pricing=_get_pricing(payload),
        provider=InferenceProviderEnum.ALIBABA_TOKEN_PLAN,
        billingType=BillingTypeEnum.SUBSCRIPTION,
        requiresConnection=True,
        supportsStructuredOutputs=False,
        supportsMeridianTools=supports_tools,
        supportedMeridianToolNames=(
            list(ALIBABA_TOKEN_PLAN_SUPPORTED_TOOL_NAMES) if supports_tools else []
        ),
        toolsSupport=supports_tools,
    )


def _build_happyhorse_model(model_id: str, operation: str) -> ModelInfo:
    input_modalities = ["text"] if operation == "t2v" else ["text", "image"]
    return ModelInfo(
        id=f"{ALIBABA_TOKEN_PLAN_MODEL_PREFIX}{model_id}",
        name=model_id,
        architecture=Architecture(
            input_modalities=input_modalities,
            modality=f"{'+'.join(input_modalities)}->video",
            output_modalities=["video"],
            tokenizer="unknown",
        ),
        pricing=Pricing(prompt="0", completion="0"),
        provider=InferenceProviderEnum.ALIBABA_TOKEN_PLAN,
        billingType=BillingTypeEnum.SUBSCRIPTION,
        requiresConnection=True,
        supportsStructuredOutputs=False,
        supportsMeridianTools=False,
        supportedMeridianToolNames=[],
        toolsSupport=False,
    )


def build_alibaba_token_plan_models_from_models_dev(
    payload: Any,
    live_model_ids: list[str] | None = None,
    official_video_model_ids: list[str] | None = None,
) -> list[ModelInfo]:
    models_payload = (
        get_models_dev_provider_models(payload, ALIBABA_TOKEN_PLAN_MODELS_DEV_PROVIDER_KEY) or {}
    )
    authoritative_ids = live_model_ids if live_model_ids is not None else list(models_payload)
    normalized_models: list[ModelInfo] = []
    seen_model_ids: set[str] = set()
    for model_id in authoritative_ids:
        if model_id in seen_model_ids:
            continue
        seen_model_ids.add(model_id)
        raw_model = models_payload.get(model_id)
        normalized_model = None
        if isinstance(raw_model, dict):
            normalized_model = normalize_alibaba_token_plan_model({"id": model_id, **raw_model})
        if normalized_model is None:
            operation = classify_happyhorse_operation(model_id)
            if operation:
                normalized_model = _build_happyhorse_model(model_id, operation)
        if normalized_model is not None:
            normalized_models.append(normalized_model)
    for model_id in official_video_model_ids or []:
        if model_id in seen_model_ids:
            continue
        seen_model_ids.add(model_id)
        operation = classify_happyhorse_operation(model_id)
        if operation:
            normalized_models.append(_build_happyhorse_model(model_id, operation))
    normalized_models.sort(key=lambda model: model.id)
    return normalized_models


def _parse_live_model_ids(payload: Any) -> list[str]:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise AlibabaTokenPlanCatalogError("Alibaba model catalog returned an invalid response.")
    data = payload["data"]
    if len(data) > MAX_CATALOG_ENTRIES:
        raise AlibabaTokenPlanCatalogError("Alibaba model catalog returned too many entries.")
    model_ids: list[str] = []
    seen: set[str] = set()
    for item in data:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        model_id = item["id"].strip()
        if (
            not model_id
            or len(model_id) > MAX_MODEL_ID_LENGTH
            or _MODEL_ID_CONTROL_RE.search(model_id)
            or model_id in seen
        ):
            continue
        seen.add(model_id)
        model_ids.append(model_id)
    return model_ids


async def _fetch_live_model_ids(api_key: str, http_client: httpx.AsyncClient) -> list[str]:
    timeout = httpx.Timeout(20.0, connect=10.0, read=20.0)
    try:
        async with http_client.stream(
            "GET",
            ALIBABA_TOKEN_PLAN_MODELS_URL,
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            timeout=timeout,
        ) as response:
            if response.status_code != 200:
                raise AlibabaTokenPlanCatalogError(
                    f"Alibaba model catalog request failed with status {response.status_code}."
                )
            content_length = response.headers.get("content-length")
            if content_length is not None:
                try:
                    declared_length = int(content_length)
                except ValueError as exc:
                    raise AlibabaTokenPlanCatalogError(
                        "Alibaba model catalog returned an invalid response size."
                    ) from exc
                if declared_length < 0 or declared_length > MAX_CATALOG_BYTES:
                    raise AlibabaTokenPlanCatalogError(
                        "Alibaba model catalog response exceeded the size limit."
                    )
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > MAX_CATALOG_BYTES:
                    raise AlibabaTokenPlanCatalogError(
                        "Alibaba model catalog response exceeded the size limit."
                    )
    except AlibabaTokenPlanCatalogError:
        raise
    except (httpx.HTTPError, TimeoutError) as exc:
        raise AlibabaTokenPlanCatalogError("Alibaba model catalog request failed.") from exc
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AlibabaTokenPlanCatalogError("Alibaba model catalog returned invalid JSON.") from exc
    return _parse_live_model_ids(payload)


async def get_alibaba_token_plan_models(
    models_dev_catalog: Any | None = None,
    *,
    api_key: str | None = None,
    http_client: httpx.AsyncClient | None = None,
    official_video_model_ids: list[str] | None = None,
) -> list[ModelInfo]:
    live_model_ids: list[str] = []
    if api_key and http_client is not None:
        live_model_ids = await _fetch_live_model_ids(api_key.strip(), http_client)
    return build_alibaba_token_plan_models_from_models_dev(
        models_dev_catalog,
        live_model_ids,
        official_video_model_ids,
    )
