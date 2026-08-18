<script setup lang="ts">
import type { ReasoningEffortEnum } from '@/types/enums';
import type { ModelInfo } from '@/types/model';
import type { ModelsSettings } from '@/types/settings';
import { getKnownReasoningEffortsUnion } from '@/utils/reasoningEffort';
import {
    REASONING_EFFORT_FIXTURE_MASKS,
    REASONING_EFFORT_FIXTURE_SELECTED,
} from '~~/e2e/fixtures/reasoningEffortFixture';
import { createNodePresetFixtureSettings } from '~~/e2e/fixtures/nodePresetsFixture';

definePageMeta({
    layout: 'blank',
});

if (!import.meta.dev) {
    throw createError({
        statusCode: 404,
        statusMessage: 'Not Found',
    });
}

const settingsStore = useSettingsStore();
const modelStore = useModelStore();

const fixtureModelsSettings: ModelsSettings = {
    defaultModel: 'fixture-account',
    routingModel: '',
    titleGenerationModel: '',
    autoToolSelectionModel: '',
    excludeReasoning: false,
    systemPrompt: [],
    reasoningEffort: REASONING_EFFORT_FIXTURE_SELECTED.account,
    preferHigherReasoningEffort: true,
    maxTokens: null,
    temperature: null,
    topP: null,
    topK: null,
    frequencyPenalty: null,
    presencePenalty: null,
    repetitionPenalty: null,
};

const createFixtureModel = (id: string, reasoningEfforts: number): ModelInfo => ({
    architecture: {
        input_modalities: ['text'],
        modality: 'text->text',
        output_modalities: ['text'],
        tokenizer: 'fixture',
    },
    id,
    name: id,
    icon: '',
    pricing: {
        completion: '0',
        prompt: '0',
    },
    provider: 'openrouter',
    billingType: 'metered',
    requiresConnection: false,
    supportsStructuredOutputs: false,
    supportsMeridianTools: false,
    supportedMeridianToolNames: [],
    toolsSupport: false,
    reasoningEfforts,
});

const fixtureModels: ModelInfo[] = [
    createFixtureModel('fixture-account', REASONING_EFFORT_FIXTURE_MASKS.highMediumLow),
    createFixtureModel('fixture-high', REASONING_EFFORT_FIXTURE_MASKS.highAndLow & 4),
    createFixtureModel('fixture-low', REASONING_EFFORT_FIXTURE_MASKS.highAndLow & 16),
    createFixtureModel('fixture-unknown', -1),
];

const fixtureSettings = createNodePresetFixtureSettings();
fixtureSettings.models = fixtureModelsSettings;
settingsStore.setUserSettings(fixtureSettings);
modelStore.setModels(fixtureModels);

const { modelsSettings } = storeToRefs(settingsStore);
const unsupportedEffort = ref<ReasoningEffortEnum>(REASONING_EFFORT_FIXTURE_SELECTED.unsupported);
const zeroEffort = ref<ReasoningEffortEnum>(REASONING_EFFORT_FIXTURE_SELECTED.zero);
const canvasEffort = ref<ReasoningEffortEnum>(REASONING_EFFORT_FIXTURE_SELECTED.canvas);
const unknownEffort = ref<ReasoningEffortEnum>(REASONING_EFFORT_FIXTURE_SELECTED.unknown);

const canvasReasoningEfforts = computed(() =>
    getKnownReasoningEffortsUnion(['fixture-high', 'fixture-low', 'fixture-unknown'], fixtureModels),
);
</script>

<template>
    <main
        data-testid="reasoning-effort-fixture-page"
        :data-prefer-higher="modelsSettings.preferHigherReasoningEffort"
        class="bg-obsidian text-soft-silk min-h-screen p-4 sm:p-8"
    >
        <div class="mx-auto flex max-w-md flex-col gap-6">
            <h1 class="text-lg font-semibold">Reasoning effort fixture</h1>

            <section
                class="w-[min(100%,28rem)]"
                data-testid="account-selector"
                :data-default-model-reasoning-efforts="REASONING_EFFORT_FIXTURE_MASKS.highMediumLow"
            >
                <h2 class="mb-2 text-sm font-medium">Unrestricted account default</h2>
                <UiSettingsSectionModelsReasoning />
            </section>

            <section class="w-[min(100%,18rem)]" data-testid="unsupported-selector">
                <h2 class="mb-2 text-sm font-medium">Unsupported saved effort</h2>
                <UiSettingsUtilsReasoningSlider
                    id="fixture-unsupported-effort"
                    :current-reasoning-effort="unsupportedEffort"
                    :reasoning-efforts="REASONING_EFFORT_FIXTURE_MASKS.highMediumLow"
                    @update:reasoning-effort="unsupportedEffort = $event"
                />
            </section>

            <section class="w-[min(100%,18rem)]" data-testid="zero-selector">
                <h2 class="mb-2 text-sm font-medium">No supported efforts</h2>
                <UiSettingsUtilsReasoningSlider
                    id="fixture-zero-effort"
                    :current-reasoning-effort="zeroEffort"
                    :reasoning-efforts="REASONING_EFFORT_FIXTURE_MASKS.none"
                    @update:reasoning-effort="zeroEffort = $event"
                />
            </section>

            <section class="w-[min(100%,18rem)]" data-testid="canvas-selector">
                <h2 class="mb-2 text-sm font-medium">Canvas capability union</h2>
                <UiSettingsUtilsReasoningSlider
                    id="fixture-canvas-effort"
                    :current-reasoning-effort="canvasEffort"
                    :reasoning-efforts="canvasReasoningEfforts"
                    @update:reasoning-effort="canvasEffort = $event"
                />
            </section>

            <section class="w-[min(100%,18rem)]" data-testid="unknown-selector">
                <h2 class="mb-2 text-sm font-medium">Unknown capability</h2>
                <UiSettingsUtilsReasoningSlider
                    id="fixture-unknown-effort"
                    :current-reasoning-effort="unknownEffort"
                    @update:reasoning-effort="unknownEffort = $event"
                />
            </section>

            <section class="flex items-center justify-between gap-4" data-testid="tie-preference">
                <span class="text-sm">Prefer higher effort on ties</span>
                <HeadlessSwitch
                    v-model="modelsSettings.preferHigherReasoningEffort"
                    data-testid="prefer-higher-switch"
                    class="bg-stone-gray data-[checked]:bg-ember-glow relative inline-flex h-6 w-11 items-center rounded-full"
                >
                    <span class="sr-only">Prefer higher effort on ties</span>
                    <span
                        class="bg-anthracite inline-block h-4 w-4 translate-x-1 rounded-full transition data-[checked]:translate-x-6"
                    />
                </HeadlessSwitch>
            </section>
        </div>
    </main>
</template>
