<script setup lang="ts">
import { ModelsDropdownSortBy } from '@/types/enums';
import type { ModelInfo } from '@/types/model';
import { decodeModelCatalog } from '@/utils/modelCatalog';
import {
    MODEL_CATALOG_FIXTURE_RESPONSE,
    MODEL_CATALOG_MODALITY_EXPECTATIONS,
} from '~~/e2e/fixtures/modelCatalogFixture';

definePageMeta({
    layout: 'blank',
});

if (!import.meta.dev) {
    throw createError({
        statusCode: 404,
        statusMessage: 'Not Found',
    });
}

const modelStore = useModelStore();
const { getAvailableModels } = useAPI();
const decoded = import.meta.client
    ? await getAvailableModels()
    : decodeModelCatalog(MODEL_CATALOG_FIXTURE_RESPONSE);

modelStore.setModels(decoded.data);
if (import.meta.client) {
    modelStore.showModelDiscoveryWarnings(decoded.warnings ?? []);
}

const fixtureIds = Object.keys(MODEL_CATALOG_MODALITY_EXPECTATIONS);
const fixtureModels = decoded.data.filter((model) => fixtureIds.includes(model.id));
const allCapabilitiesModel = modelStore.getModel('fixture-all-capabilities');
const defaultedModel = modelStore.getModel('fixture-text');

const rejectionResult = (value: unknown) => {
    const countBefore = modelStore.models.length;
    let error = '';
    try {
        const invalidCatalog = decodeModelCatalog(value);
        modelStore.setModels(invalidCatalog.data);
    } catch (decodeError: unknown) {
        error = decodeError instanceof Error ? decodeError.message : String(decodeError);
    }
    return {
        error,
        countBefore,
        countAfter: modelStore.models.length,
    };
};

const unsupportedVersion = rejectionResult({ version: 2, data: [] });
const malformedRequiredValue = rejectionResult({
    version: 1,
    data: [{ id: 'malformed', pricing: { prompt: '0', completion: '0' }, capabilities: 1 }],
});

const namedIds = (models: ModelInfo[]) =>
    models.filter((model) => fixtureIds.includes(model.id)).map((model) => model.id);

const summary = {
    modelCount: decoded.data.length,
    modalities: Object.fromEntries(
        fixtureModels.map((model) => [model.id, model.architecture.output_modalities]),
    ),
    compatible: {
        text: namedIds(modelStore.filterCompatibleModels(decoded.data, { outputModality: 'text' })),
        image: namedIds(
            modelStore.filterCompatibleModels(decoded.data, { outputModality: 'image' }),
        ),
        video: namedIds(
            modelStore.filterCompatibleModels(decoded.data, { outputModality: 'video' }),
        ),
        structured: namedIds(
            modelStore.filterCompatibleModels(decoded.data, {
                outputModality: 'image',
                requireStructuredOutputs: true,
            }),
        ),
        meridianTools: namedIds(
            modelStore.filterCompatibleModels(decoded.data, {
                outputModality: 'image',
                requireMeridianTools: true,
                requiredToolNames: ['web_search', 'ask_user'],
            }),
        ),
    },
    paid: Object.fromEntries(fixtureModels.map((model) => [model.id, modelStore.isModelPaid(model)])),
    selection: modelStore.getModel('fixture-all-capabilities').id,
    allCapabilities: {
        provider: allCapabilitiesModel.provider,
        icon: allCapabilitiesModel.icon,
        pricing: allCapabilitiesModel.pricing,
        contextLength: allCapabilitiesModel.context_length,
        billingType: allCapabilitiesModel.billingType,
        requiresConnection: allCapabilitiesModel.requiresConnection,
        structured: allCapabilitiesModel.supportsStructuredOutputs,
        nativeTools: allCapabilitiesModel.toolsSupport,
        meridianTools: allCapabilitiesModel.supportsMeridianTools,
        supportedTools: allCapabilitiesModel.supportedMeridianToolNames,
        reasoningEfforts: allCapabilitiesModel.reasoningEfforts,
    },
    defaults: {
        provider: defaultedModel.provider,
        icon: defaultedModel.icon,
        billingType: defaultedModel.billingType,
        reasoningEfforts: defaultedModel.reasoningEfforts,
        supportedTools: defaultedModel.supportedMeridianToolNames,
        requiresConnection: defaultedModel.requiresConnection,
    },
    warnings: decoded.warnings,
    unsupportedVersion,
    malformedRequiredValue,
};

modelStore.sortModels(ModelsDropdownSortBy.NAME_DESC);
const nameDescending = modelStore.models.slice(0, 3).map((model) => model.name);
modelStore.sortModels(ModelsDropdownSortBy.DATE_DESC);
const dateDescending = modelStore.models.slice(0, 3).map((model) => model.id);
modelStore.setModels(decoded.data);

const renderedSummary = {
    ...summary,
    sorting: {
        nameDescending,
        dateDescending,
    },
};
</script>

<template>
    <main
        data-testid="model-catalog-fixture-page"
        class="bg-obsidian text-soft-silk min-h-screen overflow-auto p-6"
    >
        <h1 class="text-lg font-semibold">Model catalog fixture</h1>
        <ClientOnly>
            <pre data-testid="model-catalog-summary" class="mt-4 whitespace-pre-wrap text-xs">{{
                JSON.stringify(renderedSummary)
            }}</pre>
        </ClientOnly>
    </main>
</template>
