<script setup lang="ts">
import { VueFlow, useVueFlow } from '@vue-flow/core';

import type { QuickWorkflowCreatePayload } from '@/composables/useGraphEvents';
import { AUTO_PLACEMENT_GAP } from '@/composables/useGraphOverlaps';
import { NodeCategoryEnum, NodeTypeEnum } from '@/types/enums';
import type { Settings } from '@/types/settings';
import {
    QUICK_WORKFLOW_FIXTURE_BLOCK_SETTINGS,
    QUICK_WORKFLOW_FIXTURE_GRAPH_ID,
    QUICK_WORKFLOW_SETTINGS_KEYS,
} from '~~/e2e/fixtures/quickWorkflowWheelFixture';

definePageMeta({ layout: false });
if (!import.meta.dev) {
    throw createError({ statusCode: 404, statusMessage: 'Not Found' });
}

const settingsStore = useSettingsStore();
settingsStore.setUserSettings({
    block: structuredClone(QUICK_WORKFLOW_FIXTURE_BLOCK_SETTINGS),
    models: {
        defaultModel: '',
        routingModel: '',
        titleGenerationModel: '',
        autoToolSelectionModel: '',
        excludeReasoning: false,
        systemPrompt: [],
        reasoningEffort: null,
        preferHigherReasoningEffort: true,
        maxTokens: null,
        temperature: null,
        topP: null,
        topK: null,
        frequencyPenalty: null,
        presencePenalty: null,
        repetitionPenalty: null,
    },
    blockParallelization: { models: [], aggregator: { prompt: '', model: '' } },
    blockRouting: { routeGroups: [] },
    blockContextMerger: {
        merger_mode: 'full',
        last_n: 5,
        summarizer_model: '',
        include_user_messages: true,
    },
    tools: { defaultSelectedTools: [], defaultAutoSelectTools: false },
} as unknown as Settings);

const graphId = ref(QUICK_WORKFLOW_FIXTURE_GRAPH_ID);
const GENERATOR_ANCHOR_POSITION = { x: 600, y: 550 };
const ATTACHMENT_ANCHOR_POSITION = { x: 1500, y: 550 };
const ATTACHMENT_TARGET_MAIN_WIDTH = 500;
const ATTACHMENT_SOURCE_ANCHOR_WIDTH = 300;
const CONTEXT_MAIN_HEIGHT = 300;
const seedNodes = () => [
    {
        id: 'generator-anchor',
        type: NodeTypeEnum.TEXT_TO_TEXT,
        position: { ...GENERATOR_ANCHOR_POSITION },
        data: {},
        width: 300,
        height: 180,
    },
    {
        id: 'prompt-anchor',
        type: NodeTypeEnum.PROMPT,
        position: { x: 1100, y: 550 },
        data: {},
        width: 300,
        height: 180,
    },
    {
        id: 'attachment-anchor',
        type: NodeTypeEnum.FILE_PROMPT,
        position: { ...ATTACHMENT_ANCHOR_POSITION },
        data: {},
        width: 300,
        height: 180,
    },
];
const nodes = ref(seedNodes());
const edges = ref([]);
const { setNodes, setEdges, updateNode, getNodes, getEdges } = useVueFlow(
    'main-graph-' + QUICK_WORKFLOW_FIXTURE_GRAPH_ID,
);
const { createQuickWorkflow } = useQuickWorkflow(graphId);
const graphEvents = useGraphEvents();
const { blockSettings } = storeToRefs(settingsStore);
const fixtureReady = ref(false);

const resetGraph = () => {
    setNodes(seedNodes());
    setEdges([]);
};
const forceAttachmentCollision = (direction: 'target' | 'source') => {
    const position =
        direction === 'target'
            ? {
                  x:
                      GENERATOR_ANCHOR_POSITION.x -
                      ATTACHMENT_TARGET_MAIN_WIDTH -
                      AUTO_PLACEMENT_GAP,
                  y: GENERATOR_ANCHOR_POSITION.y,
              }
            : {
                  x:
                      ATTACHMENT_ANCHOR_POSITION.x +
                      ATTACHMENT_SOURCE_ANCHOR_WIDTH +
                      AUTO_PLACEMENT_GAP,
                  y: ATTACHMENT_ANCHOR_POSITION.y,
              };
    updateNode('prompt-anchor', { position });
};
const forceDefaultTargetCollision = () => {
    updateNode('prompt-anchor', {
        position: {
            x: 400,
            y: GENERATOR_ANCHOR_POSITION.y - CONTEXT_MAIN_HEIGHT - AUTO_PLACEMENT_GAP,
        },
    });
};
const mutateWheel = (key: (typeof QUICK_WORKFLOW_SETTINGS_KEYS)[number]) => {
    blockSettings.value[key][0]!.name = `${key}-changed`;
};
const runStalePreset = () => {
    const payload: QuickWorkflowCreatePayload = {
        fromNodeId: 'generator-anchor',
        category: NodeCategoryEnum.CONTEXT,
        direction: 'source',
        slot: { name: 'Invalid', mainBloc: NodeTypeEnum.PROMPT, options: [] },
    };
    createQuickWorkflow(payload);
};
const runOccupiedPromptTarget = async () => {
    setEdges([
        {
            id: 'occupied-prompt-edge',
            source: 'prompt-anchor',
            target: 'prompt-anchor',
            sourceHandle: 'prompt_prompt-anchor',
            targetHandle: 'prompt_prompt-anchor',
        },
    ]);
    await nextTick();
    createQuickWorkflow({
        fromNodeId: 'prompt-anchor',
        category: NodeCategoryEnum.PROMPT,
        direction: 'target',
        slot: blockSettings.value.promptInputWheel[0]!,
    });
};
const state = computed(() => ({
    wheels: Object.fromEntries(
        QUICK_WORKFLOW_SETTINGS_KEYS.map((key) => [
            key,
            blockSettings.value[key].map((wheelSlot) => wheelSlot.name),
        ]),
    ),
    nodes: getNodes.value.map((node) => ({
        id: node.id,
        type: node.type,
        position: node.position,
        dimensions: {
            width:
                node.dimensions.width || (typeof node.width === 'number' ? node.width : 0),
            height:
                node.dimensions.height || (typeof node.height === 'number' ? node.height : 0),
        },
    })),
    edges: getEdges.value.map((edge) => ({
        source: edge.source,
        target: edge.target,
        sourceHandle: edge.sourceHandle,
        targetHandle: edge.targetHandle,
    })),
}));

onMounted(() => {
    const unsubscribe = graphEvents.on('node-create', createQuickWorkflow);
    onUnmounted(unsubscribe);
    fixtureReady.value = true;
});
</script>

<template>
    <main
        data-testid="quick-workflow-fixture-page"
        :data-fixture-ready="fixtureReady"
        class="bg-obsidian text-soft-silk h-screen w-screen overflow-auto p-4"
    >
        <div class="mb-4 flex flex-wrap gap-2">
            <button data-testid="reset-graph" @click="resetGraph">Reset graph</button>
            <button data-testid="run-stale-preset" @click="runStalePreset">Run stale preset</button>
            <button data-testid="run-occupied-prompt" @click="runOccupiedPromptTarget">
                Run occupied prompt
            </button>
            <button
                data-testid="force-attachment-target-collision"
                @click="forceAttachmentCollision('target')"
            >
                Force attachment target collision
            </button>
            <button
                data-testid="force-attachment-source-collision"
                @click="forceAttachmentCollision('source')"
            >
                Force attachment source collision
            </button>
            <button
                data-testid="force-default-target-collision"
                @click="forceDefaultTargetCollision"
            >
                Force default target collision
            </button>
            <button
                v-for="key in QUICK_WORKFLOW_SETTINGS_KEYS"
                :key="key"
                :data-testid="`mutate-${key}`"
                @click="mutateWheel(key)"
            >
                Mutate {{ key }}
            </button>
        </div>

        <pre data-testid="quick-workflow-state" class="mb-4 max-w-full whitespace-pre-wrap break-all text-xs">{{
            JSON.stringify(state)
        }}</pre>
        <div class="h-[900px] w-full" data-testid="quick-workflow-graph">
            <VueFlow
                :id="`main-graph-${graphId}`"
                :nodes="nodes"
                :edges="edges"
                :min-zoom="0.2"
                :max-zoom="1"
                :default-viewport="{ x: 0, y: 0, zoom: 0.55 }"
                :fit-view-on-init="false"
            >
                <template #node-textToText="nodeProps">
                    <div
                        class="bg-olive-grove relative h-full w-full rounded-xl p-4 text-black"
                        data-testid="generator-anchor-node"
                        :style="
                            nodeProps.id === 'generator-anchor'
                                ? undefined
                                : { width: '600px', height: '300px' }
                        "
                    >
                        Generator {{ nodeProps.id }}
                        <UiGraphNodeUtilsHandleContext
                            :id="nodeProps.id"
                            type="target"
                            :is-dragging="false"
                            :style="{ left: '66%' }"
                            multiple-input
                        />
                        <UiGraphNodeUtilsHandlePrompt
                            :id="nodeProps.id"
                            type="target"
                            :is-dragging="false"
                            :style="{ left: '33%' }"
                        />
                        <UiGraphNodeUtilsHandleAttachment :id="nodeProps.id" type="target" :is-dragging="false" />
                        <UiGraphNodeUtilsHandleContext :id="nodeProps.id" type="source" :is-dragging="false" />
                    </div>
                </template>
                <template #node-prompt="nodeProps">
                    <div
                        class="bg-slate-blue relative h-full w-full rounded-xl p-4"
                        :style="
                            nodeProps.id === 'prompt-anchor'
                                ? undefined
                                : { width: '500px', height: '200px' }
                        "
                    >
                        Prompt {{ nodeProps.id }}
                        <UiGraphNodeUtilsHandlePrompt :id="nodeProps.id" type="target" :is-dragging="false" />
                        <UiGraphNodeUtilsHandlePrompt :id="nodeProps.id" type="source" :is-dragging="false" />
                    </div>
                </template>
                <template #node-filePrompt="nodeProps">
                    <div class="bg-dried-heather relative h-full w-full rounded-xl p-4 text-black">
                        Attachment {{ nodeProps.id }}
                        <UiGraphNodeUtilsHandleAttachment :id="nodeProps.id" type="source" :is-dragging="false" />
                    </div>
                </template>
            </VueFlow>
        </div>

        <section class="mt-8 max-w-5xl" data-testid="wheel-settings-editors">
            <UiSettingsSectionBlocks />
        </section>
    </main>
</template>
