from models.inference import BillingTypeEnum, ModelInfo, ResponseModel
from models.message import ToolEnum
from schemas.model_catalog import CompactModelCatalogResponse, CompactModelInfo, CompactModelPricing

CAPABILITY_TEXT_OUTPUT = 1 << 0
CAPABILITY_IMAGE_OUTPUT = 1 << 1
CAPABILITY_VIDEO_OUTPUT = 1 << 2
CAPABILITY_STRUCTURED_OUTPUTS = 1 << 3
CAPABILITY_NATIVE_TOOLS = 1 << 4
CAPABILITY_MERIDIAN_TOOLS = 1 << 5
CAPABILITY_SUBSCRIPTION = 1 << 6

CAPABILITY_BITS = {
    "text_output": CAPABILITY_TEXT_OUTPUT,
    "image_output": CAPABILITY_IMAGE_OUTPUT,
    "video_output": CAPABILITY_VIDEO_OUTPUT,
    "structured_outputs": CAPABILITY_STRUCTURED_OUTPUTS,
    "native_tools": CAPABILITY_NATIVE_TOOLS,
    "meridian_tools": CAPABILITY_MERIDIAN_TOOLS,
    "subscription": CAPABILITY_SUBSCRIPTION,
}

MERIDIAN_TOOL_BITS = {
    ToolEnum.WEB_SEARCH.value: 1 << 0,
    ToolEnum.LINK_EXTRACTION.value: 1 << 1,
    ToolEnum.IMAGE_GENERATION.value: 1 << 2,
    ToolEnum.EXECUTE_CODE.value: 1 << 3,
    ToolEnum.VISUALISE.value: 1 << 4,
    ToolEnum.ASK_USER.value: 1 << 5,
}

_ALL_WIRE_BITS = (*CAPABILITY_BITS.values(), *MERIDIAN_TOOL_BITS.values())
assert len(CAPABILITY_BITS.values()) == len(set(CAPABILITY_BITS.values()))
assert len(MERIDIAN_TOOL_BITS.values()) == len(set(MERIDIAN_TOOL_BITS.values()))
assert all(0 <= bit <= 0x7FFFFFFF for bit in _ALL_WIRE_BITS)


def _encode_capabilities(model: ModelInfo) -> int:
    capabilities = 0
    output_modalities = model.architecture.output_modalities
    if "text" in output_modalities:
        capabilities |= CAPABILITY_TEXT_OUTPUT
    if "image" in output_modalities:
        capabilities |= CAPABILITY_IMAGE_OUTPUT
    if "video" in output_modalities:
        capabilities |= CAPABILITY_VIDEO_OUTPUT
    if model.supportsStructuredOutputs:
        capabilities |= CAPABILITY_STRUCTURED_OUTPUTS
    if model.toolsSupport:
        capabilities |= CAPABILITY_NATIVE_TOOLS
    if model.supportsMeridianTools:
        capabilities |= CAPABILITY_MERIDIAN_TOOLS
    if model.billingType == BillingTypeEnum.SUBSCRIPTION:
        capabilities |= CAPABILITY_SUBSCRIPTION
    return capabilities


def _encode_supported_tools(model: ModelInfo) -> int:
    supported_tools = 0
    for tool_name in model.supportedMeridianToolNames:
        supported_tools |= MERIDIAN_TOOL_BITS.get(tool_name, 0)
    return supported_tools


def encode_model_catalog(response: ResponseModel) -> CompactModelCatalogResponse:
    """Convert an internal model catalog into the version-1 endpoint wire shape."""

    data = [
        CompactModelInfo(
            id=model.id,
            name=model.name,
            icon=model.icon,
            provider=model.provider,
            created=model.created,
            contextLength=model.context_length,
            pricing=CompactModelPricing(
                prompt=model.pricing.prompt,
                completion=model.pricing.completion,
                image=model.pricing.image,
            ),
            capabilities=_encode_capabilities(model),
            supportedTools=_encode_supported_tools(model),
            reasoningEfforts=model.reasoningEfforts,
        )
        for model in response.data
    ]
    return CompactModelCatalogResponse(version=1, data=data, warnings=list(response.warnings))
