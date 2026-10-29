<script setup lang="ts">
import { NodeTypeEnum, MessageContentTypeEnum, MessageRoleEnum, ToolEnum } from '@/types/enums';
import { VueFlow, type Node } from '@vue-flow/core';
import type { DataAgent, SidebarNode } from '@/types/graph';
import { createNodePresetFixtureSettings } from '~~/e2e/fixtures/nodePresetsFixture';
import type { AgentRun } from '@/types/agent';
import { AGENT_SETTINGS_MODELS } from '~~/e2e/fixtures/agentSettingsFixture';
definePageMeta({ layout: false });
if (!import.meta.dev) throw createError({ statusCode: 404, statusMessage: 'Not Found' });
const settingsView = useRoute().query.view === 'settings';
const compactView = useRoute().query.view === 'node';
const sidebarView = useRoute().query.view === 'sidebar';
const canvasView = useRoute().query.view === 'canvas';
const fixtureSettings = createNodePresetFixtureSettings();
fixtureSettings.models.defaultModel = 'fixture/default';
useSettingsStore().setUserSettings(fixtureSettings);
{
    const models = useModelStore();
    models.setModels(AGENT_SETTINGS_MODELS);
    models.triggerFilter();
    useState<boolean>('inference-provider-statuses-loaded', () => false).value = true;
}
const store = useAgentStore();
const model = ref('fixture/default');
const responseMessage = computed(() => ({
    role: MessageRoleEnum.assistant,
    type: NodeTypeEnum.AGENT,
    model: model.value,
    node_id: 'fixture',
    data: null,
    usageData: null,
    content: [
        {
            type: MessageContentTypeEnum.TEXT,
            text: '[THINK]Review the evidence.[!THINK]\nMain model final answer.',
        },
    ],
}));
const tools = ref<ToolEnum[]>([]);
const team = ref('');
const previewData = reactive<DataAgent>({
    model: 'fixture/default',
    teamId: '',
    selectedTools: [],
    reply: 'Final answer from the main model.',
    agentExecution: {
        runs: {
            main: {
                id: 'preview-main',
                parent_id: null,
                agent_id: null,
                name: 'Main model',
                status: 'completed',
            },
            first: {
                id: 'preview-first',
                parent_id: 'preview-main',
                agent_id: 'researcher',
                name: 'Researcher',
                status: 'completed',
            },
            second: {
                id: 'preview-second',
                parent_id: 'preview-main',
                agent_id: 'reviewer',
                name: 'Reviewer',
                status: 'completed',
            },
        },
    },
});
const sidebarNode: SidebarNode<DataAgent> = {
    id: 'fixture',
    type: NodeTypeEnum.AGENT,
    position: { x: 0, y: 0 },
    data: previewData,
};
const setPreviewData = (key: string, value: RuntimeValue) => {
    if (key === 'model' && isRuntimeString(value)) previewData.model = value;
    else if (key === 'autoSelectTools' && isRuntimeBoolean(value))
        previewData.autoSelectTools = value;
    else if (key === 'teamId' && isRuntimeString(value)) previewData.teamId = value;
    else if (key === 'selectedTools' && Array.isArray(value))
        previewData.selectedTools = value.filter((item): item is ToolEnum =>
            Object.values(ToolEnum).some((tool) => tool === item),
        );
};
const canvasNodes = shallowRef<Node<DataAgent>[]>([
    {
        id: 'preview-agent',
        type: NodeTypeEnum.AGENT,
        position: { x: 24, y: 24 },
        data: previewData,
        style: { width: '700px', height: '380px' },
    },
]);
const ready = ref(false);
const status = ref('');
const mutations = ref(0);
const submit = async (submission: { message: string }, restore: () => void) => {
    try {
        const resolved = await store.resolveMention(submission.message);
        status.value = resolved.team_id ?? 'main model';
        if (resolved.team_id) team.value = resolved.team_id;
        mutations.value += 1;
    } catch (err) {
        status.value = runtimeErrorDetail(err) ?? 'Invalid Agent mention';
        restore();
    }
};
const run = (id: string, name: string, instructions: string): AgentRun => ({
    id,
    parent_id: 'primary-run',
    agent_id: id,
    name,
    handle: id,
    version: 1,
    instructions,
    status: 'running',
    result: '',
    error: null,
    tool_calls: [],
});
const parallel = () => {
    store.runs['fixture'] = {
        primary: {
            ...run('primary-run', 'Main model', ''),
            parent_id: null,
            agent_id: null,
            version: null,
            status: 'completed',
            result: 'Final answer already shown in chat',
        },
        first: run('first', 'Researcher', 'Find evidence'),
        second: run('second', 'Reviewer', 'Review findings'),
    };
};
const finishFirst = () => {
    store.appendRunChunk('fixture', 'first', 'Evidence collected');
    const first = store.runs['fixture']?.first;
    if (first) {
        first.status = 'completed';
        first.tool_calls.push({
            id: 'tool-first',
            name: 'web_search',
            arguments: { query: 'evidence' },
            result: { found: true },
        });
    }
};
const longRun = () => {
    parallel();
    const first = store.runs.fixture?.first;
    if (first)
        first.result =
            Array.from(
                { length: 60 },
                (_, index) =>
                    `Finding ${index + 1}: Evidence collected from a source, with context and analysis.`,
            ).join('\n\n') + '\n\nLatest finding.';
};
let appendedFindings = 0;
const appendFinding = () => {
    const first = store.runs.fixture?.first;
    if (first) first.result += `\n\nNew streamed finding ${++appendedFindings}.`;
};
onMounted(async () => {
    await store.loadLibrary();
    ready.value = true;
});
</script>

<template>
    <main
        class="bg-obsidian text-soft-silk h-screen w-full overflow-y-auto p-8"
        data-testid="agent-fixture"
        :data-ready="ready"
    >
        <div v-if="settingsView" class="mx-auto max-w-7xl"><UiSettingsSectionBlocksAgent /></div>
        <section v-else-if="sidebarView" class="mx-auto flex max-w-md flex-col gap-6">
            <UiGraphSidebarNodeDataAgent :node="sidebarNode" :set-node-data-key="setPreviewData" />
            <output data-testid="auto-select-tools">{{
                previewData.autoSelectTools ?? false
            }}</output>
            <output data-testid="selected-tools">{{ previewData.selectedTools.join(',') }}</output>
        </section>
        <section v-else-if="canvasView" class="h-128 w-full" aria-label="Agent node preview">
            <ClientOnly>
                <VueFlow
                    id="agent-appearance-fixture"
                    :nodes="canvasNodes"
                    :edges="[]"
                    :nodes-draggable="false"
                >
                    <template #node-agent="nodeProps">
                        <UiGraphNodeAgent
                            v-bind="nodeProps"
                            preset-editor
                            :is-graph-name-default="false"
                        />
                    </template>
                </VueFlow>
            </ClientOnly>
        </section>
        <template v-else>
            <h1 class="mb-5 text-xl">Agent execution fixture</h1>
            <UiLibraryAgentSelection
                :compact="compactView"
                :model="model"
                :selected-tools="tools"
                :team-id="team"
                @model="model = $event"
                @team="team = $event"
            />
            <output data-testid="configuration">{{ model }} / {{ team }}</output>
            <div class="relative mt-8">
                <UiChatTextInput
                    :is-locked-to-bottom="true"
                    :is-streaming="false"
                    :node-type="NodeTypeEnum.AGENT"
                    from="chat"
                    @generate="submit"
                />
            </div>
            <output data-testid="mention-status">{{ status }}</output>
            <output data-testid="mutation-count">{{ mutations }}</output>
            <div class="my-5 flex flex-wrap gap-4">
                <button @click="parallel">Start parallel batch</button
                ><button @click="finishFirst">Finish first run</button>
                <button @click="longRun">Start long subagent</button>
                <button @click="appendFinding">Append finding</button>
            </div>
            <UiChatMarkdownRenderer :message="responseMessage" :edit-mode="false">
                <template #activity><UiLibraryAgentActivity node-id="fixture" /></template>
            </UiChatMarkdownRenderer>
        </template>
    </main>
</template>
