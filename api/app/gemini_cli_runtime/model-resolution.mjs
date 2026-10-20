import {
    DEFAULT_GEMINI_MODEL_AUTO,
    GEMINI_MODEL_ALIAS_AUTO,
    PREVIEW_GEMINI_MODEL_AUTO,
    resolveModel,
} from '@google/gemini-cli-core';

export const resolveRequestedModel = (requestedModel, previewFeaturesEnabled) => {
    const modelToResolve =
        requestedModel === GEMINI_MODEL_ALIAS_AUTO
            ? previewFeaturesEnabled
                ? PREVIEW_GEMINI_MODEL_AUTO
                : DEFAULT_GEMINI_MODEL_AUTO
            : requestedModel;

    return resolveModel(modelToResolve, false, false, previewFeaturesEnabled);
};
