from typing import Any

import httpx

MODELS_DEV_API_URL = "https://models.dev/api.json"
MODELS_DEV_USED_PROVIDER_KEYS = ("openai", "zai-coding-plan")


def reduce_models_dev_catalog(payload: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(payload, dict):
        return {}

    catalog: dict[str, dict[str, Any]] = {}
    for provider_key in MODELS_DEV_USED_PROVIDER_KEYS:
        provider_payload = payload.get(provider_key)
        if not isinstance(provider_payload, dict):
            continue

        models_payload = provider_payload.get("models")
        if not isinstance(models_payload, dict):
            continue

        catalog[provider_key] = {
            "models": {
                str(model_id): raw_model
                for model_id, raw_model in models_payload.items()
                if model_id and isinstance(raw_model, dict)
            }
        }

    return catalog


def get_models_dev_provider_models(
    catalog: Any,
    provider_key: str,
) -> dict[str, Any]:
    if not isinstance(catalog, dict):
        return {}

    provider_payload = catalog.get(provider_key)
    if not isinstance(provider_payload, dict):
        return {}

    models_payload = provider_payload.get("models")
    if not isinstance(models_payload, dict):
        return {}
    return models_payload


async def fetch_models_dev_catalog(http_client: httpx.AsyncClient) -> dict[str, dict[str, Any]]:
    response = await http_client.get(MODELS_DEV_API_URL)
    response.raise_for_status()
    return reduce_models_dev_catalog(response.json())
