<script setup lang="ts">
import { VueFlow, useVueFlow, type GraphNode } from '@vue-flow/core';

import { NodeTypeEnum } from '@/types/enums';
import type { Settings } from '@/types/settings';
import type { User } from '@/types/user';
import {
    CANVAS_QUICK_ACTION_GRAPH_ID,
} from '~~/e2e/fixtures/canvasQuickActionWheelFixture';
import {
    GITHUB_PLACEMENT_PRESET,
    INVALID_PLACEMENT_PRESET,
    PLACEMENT_PRESET,
} from '~~/e2e/fixtures/nodePresetsFixture';
import { QUICK_WORKFLOW_FIXTURE_BLOCK_SETTINGS } from '~~/e2e/fixtures/quickWorkflowWheelFixture';

definePageMeta({ layout: false });
if (!import.meta.dev) throw createError({ statusCode: 404, statusMessage: 'Not Found' });

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
    nodePresets: { schemaVersion: 1, presets: [] },
} as unknown as Settings);
const { user, session } = useUserSession();
const setPlan = (plan: 'free' | 'premium') => {
    session.value = { id: 'canvas-quick-action-fixture-session', user: {
        id: 'canvas-fixture-user',
        oauthId: 'canvas-fixture-oauth',
        email: 'fixture@example.com',
        name: 'Canvas Fixture',
        avatarUrl: '',
        provider: 'userpass',
        plan_type: plan,
        is_admin: false,
        is_verified: true,
        has_seen_welcome: true,
    } satisfies User };
};
setPlan('premium');

const graphId = ref(CANVAS_QUICK_ACTION_GRAPH_ID);
const seedNodes = (): GraphNode[] => [
    {
        id: 'selected-a',
        type: NodeTypeEnum.TEXT_TO_TEXT,
        position: { x: 180, y: 180 },
        width: 220,
        height: 120,
        selected: true,
        data: { label: 'Selected A' },
    } as GraphNode,
    {
        id: 'selected-b',
        type: NodeTypeEnum.PROMPT,
        position: { x: 520, y: 180 },
        width: 220,
        height: 120,
        selected: true,
        data: { label: 'Selected B' },
    } as GraphNode,
    {
        id: 'unselected',
        type: NodeTypeEnum.TEXT_TO_TEXT,
        position: { x: 860, y: 180 },
        width: 220,
        height: 120,
        data: { label: 'Unselected' },
    } as GraphNode,
];
const nodes = shallowRef(seedNodes());
const seedEdges = () => [
    {
        id: 'fixture-edge',
        source: 'selected-a',
        target: 'selected-b',
        type: 'default',
    },
];
const edges = ref(seedEdges());
const {
    getNodes,
    getEdges,
    setNodes,
    setEdges,
    removeNodes,
    project,
    addSelectedNodes,
    panBy,
    fitView,
} = useVueFlow('main-graph-' + graphId.value);
const isOverSidebar = ref(false);
const { isSelecting, selectionRect, onSelectionStart } = useGraphSelection(
    getNodes,
    project,
    addSelectedNodes,
    panBy,
    isOverSidebar,
    isOverSidebar,
);

const deleteNode = (nodeId: string) => {
    removeNodes(getNodes.value.filter((node) => node.id === nodeId));
};
const unlinkNode = (nodeId: string) => {
    const node = getNodes.value.find((candidate) => candidate.id === nodeId);
    if (node) node.parentNode = undefined;
};
const deleteGroup = (_graphId: string, groupId: string) => deleteNode(groupId);
const quickActions = useGraphQuickActions({
    graphId,
    onSelectionStart,
    deleteNode,
    unlinkNode,
    deleteGroup,
    fitGraph: () => fitView({ padding: 0.2 }),
});
const graphContainer = ref<HTMLElement | null>(null);
const fixtureReady = ref(false);
const actionLog = ref<string[]>([]);

const activate = (action: GraphQuickAction) => {
    actionLog.value.push(action.id);
    quickActions.activate(action);
};
const onKeyDown = (event: KeyboardEvent) => {
    if (graphContainer.value) quickActions.onKeyboardContextMenu(event, graphContainer.value);
};
const reset = () => {
    setNodes(seedNodes());
    setEdges(seedEdges());
    settingsStore.nodePresetSettings.presets.splice(0);
    setPlan('premium');
    actionLog.value = [];
    quickActions.close(false);
};
const seedPresets = (kind: 'valid' | 'invalid' | 'github') => {
    const preset =
        kind === 'valid'
            ? PLACEMENT_PRESET
            : kind === 'github'
              ? GITHUB_PLACEMENT_PRESET
              : INVALID_PLACEMENT_PRESET;
    settingsStore.nodePresetSettings.presets.splice(0, Infinity, structuredClone(preset));
    setPlan(kind === 'github' ? 'free' : 'premium');
    quickActions.close(false);
};
const state = computed(() => ({
    nodeIds: getNodes.value.map((node) => node.id),
    selectedIds: getNodes.value.filter((node) => node.selected).map((node) => node.id),
    nodes: getNodes.value.map((node) => ({
        id: node.id,
        type: node.type,
        position: node.position,
        parentNode: node.parentNode,
        data: node.data,
    })),
    edges: getEdges.value.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        sourceHandle: edge.sourceHandle,
        targetHandle: edge.targetHandle,
    })),
    presetNames: settingsStore.nodePresetSettings.presets.map((preset) => preset.name),
    plan: (user.value as User | null)?.plan_type ?? null,
    actions: actionLog.value,
    selecting: isSelecting.value,
}));

onMounted(async () => {
    await nextTick();
    fixtureReady.value = true;
});
</script>

<template>
    <main
        data-testid="canvas-quick-action-fixture-page"
        :data-fixture-ready="fixtureReady"
        class="bg-obsidian text-soft-silk h-screen w-screen overflow-hidden"
    >
        <button data-testid="reset-quick-actions" class="absolute top-2 left-2 z-30" @click="reset">
            Reset
        </button>
        <div class="absolute top-8 left-2 z-30 flex gap-2">
            <button data-testid="seed-valid-preset" @click="seedPresets('valid')">Seed valid preset</button>
            <button data-testid="seed-invalid-preset" @click="seedPresets('invalid')">Seed invalid preset</button>
            <button data-testid="seed-github-preset" @click="seedPresets('github')">Seed GitHub preset</button>
        </div>
        <pre data-testid="canvas-quick-action-state" class="absolute top-2 left-20 z-30 text-xs">{{
            JSON.stringify(state)
        }}</pre>
        <div
            ref="graphContainer"
            data-testid="canvas-quick-action-graph"
            tabindex="0"
            aria-label="Quick action fixture graph"
            class="h-full w-full"
            @mousedown="quickActions.onPointerDown"
            @contextmenu="quickActions.onContextMenu"
            @keydown="onKeyDown"
        >
            <VueFlow
                :id="`main-graph-${graphId}`"
                :nodes="nodes"
                :edges="edges"
                :default-viewport="{ x: 80, y: 180, zoom: 0.7 }"
                :fit-view-on-init="false"
                :delete-key-code="null"
            >
                <template #node-textToText="nodeProps">
                    <div class="bg-olive-grove h-full w-full rounded-xl p-4 text-black">
                        {{ nodeProps.data.label ?? nodeProps.id }}
                        <input
                            v-if="nodeProps.id === 'unselected'"
                            data-testid="editable-node-input"
                            value="Editable"
                            class="nodrag mt-3 block"
                        >
                    </div>
                </template>
                <template #node-prompt="nodeProps">
                    <div class="bg-slate-blue h-full w-full rounded-xl p-4">
                        {{ nodeProps.data.label ?? nodeProps.id }}
                    </div>
                </template>
                <template #node-group="nodeProps">
                    <div class="h-full w-full rounded-xl border border-dashed border-blue-400 p-4">
                        {{ nodeProps.data.title ?? nodeProps.id }}
                    </div>
                </template>
            </VueFlow>

            <div
                v-if="isSelecting"
                data-testid="fixture-selection-rect"
                class="pointer-events-none fixed border-2 border-dashed border-blue-500"
                :style="{
                    left: `${selectionRect.x}px`,
                    top: `${selectionRect.y}px`,
                    width: `${selectionRect.width}px`,
                    height: `${selectionRect.height}px`,
                }"
            />
        </div>

        <UiGraphQuickActionWheel
            v-if="quickActions.isOpen.value"
            :actions="quickActions.actions.value"
            :x="quickActions.position.value.x"
            :y="quickActions.position.value.y"
            @activate="activate"
            @close="quickActions.close"
        />
    </main>
</template>
