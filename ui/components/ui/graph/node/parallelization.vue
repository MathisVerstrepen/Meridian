<script lang="ts" setup>
import { Position, Handle, type NodeProps } from '@vue-flow/core';
import { NodeResizer } from '@vue-flow/node-resizer';

import { AVAILABLE_WHEELS } from '@/constants';
import type { DataParallelization } from '@/types/graph';
import { NodeTypeEnum } from '@/types/enums';

const emit = defineEmits(['updateNodeInternals', 'update:canvasName', 'update:deleteNode']);

// --- Stores ---
const canvasSaveStore = useCanvasSaveStore();
const streamStore = useStreamStore();
const chatStore = useChatStore();
const globalSettingsStore = useSettingsStore();

// --- State from Stores ---
const { currentModel } = storeToRefs(chatStore);
const { blockSettings, isReady } = storeToRefs(globalSettingsStore);

// --- Actions/Methods from Stores ---
const { saveGraph } = canvasSaveStore;
const { startStream, setCanvasCallback, preStreamSession } = streamStore;
const { loadAndOpenChat } = chatStore;

// --- Composables ---
const { handleConnectableInputContext, handleConnectableInputPrompt } = useEdgeCompatibility();
const { getGenerateParallelizationAggregatorStream } = useAPI();
const { addChunkCallbackBuilder, addChunkCallbackBuilderWithId } = useStreamCallbacks();
const { getBlockById } = useBlocks();
const { generateId } = useUniqueId();

// --- Routing ---
const route = useRoute();
const graphId = computed(() => (route.params.id as string) ?? '');

// --- Props ---
const props = defineProps<NodeProps<DataParallelization> & { isGraphNameDefault: boolean }>();

// --- Local State ---
const isStreaming = ref(false);
const doneModels = ref(0);
const blockDefinition = getBlockById('primary-model-parallelization');

// --- Computed Properties ---
const minHeight = computed(() => {
    return (
        (blockDefinition?.minSize?.height || 100) +
        (Math.ceil(props.data.models.length / 2) - 1) * 168 +
        (props.data.models.length > 2 ? 8 : 0)
    );
});

// --- Core Logic Functions ---
const addParallelizationModel = () => {
    if (!props.data) return;

    const newModel = {
        model: props.data.defaultModel,
        reply: '',
        id: generateId(),
    };

    props.data.models.push(newModel);
};

const addChunkModels = addChunkCallbackBuilderWithId(
    (modelId: string) => {
        const model = props.data.models.find((m) => m.id === modelId);
        if (model) model.reply = '';
    },
    () => {
        doneModels.value += 1;
    },
    (usageData: any, modelId: string) => {
        const model = props.data.models.find((m) => m.id === modelId);
        if (model) model.usageData = usageData;
    },
    (chunk: string, modelId: string) => {
        const model = props.data.models.find((m) => m.id === modelId);
        if (model) model.reply += chunk;
    },
);

const addChunkAggregator = addChunkCallbackBuilder(
    () => {
        props.data.aggregator.reply = '';
        isStreaming.value = true;
    },
    async () => {
        isStreaming.value = false;
        await saveGraph();
    },
    (usageData: any) => {
        props.data.usageData = usageData;
    },
    (chunk: string) => {
        if (props.data) props.data.aggregator.reply += chunk;
    },
);

const sendPrompt = async () => {
    if (!props.data) return;

    isStreaming.value = true;
    doneModels.value = 0;
    props.data.aggregator.reply = '';

    let jobs: Promise<StreamSession | undefined>[] = [];

    preStreamSession(props.id, NodeTypeEnum.PARALLELIZATION);

    for (const model of props.data.models) {
        model.reply = '';

        setCanvasCallback(model.id, NodeTypeEnum.TEXT_TO_TEXT, async (chunk: string) => {
            addChunkModels(chunk, model.id);
        });

        const job = startStream(
            model.id,
            NodeTypeEnum.TEXT_TO_TEXT,
            {
                graph_id: graphId.value,
                node_id: props.id,
                model: model.model,
            },
            false,
        );
        jobs.push(job);
    }

    await Promise.all(jobs);

    // wait for all models to finish
    while (doneModels.value !== props.data.models.length) {
        await new Promise((resolve) => setTimeout(resolve, 100));
    }

    await saveGraph();

    setCanvasCallback(props.id, NodeTypeEnum.PARALLELIZATION, addChunkAggregator);

    const session = await startStream(
        props.id,
        NodeTypeEnum.PARALLELIZATION,
        {
            graph_id: graphId.value,
            node_id: props.id,
            model: props.data.aggregator.model,
        },
        props.isGraphNameDefault,
        getGenerateParallelizationAggregatorStream,
    );

    if (props.isGraphNameDefault) {
        emit('update:canvasName', session?.titleResponse);
    }
};

const openChat = async () => {
    // setCanvasCallback(props.id, addChunkAggregator);
    currentModel.value = props.data.aggregator.model;
    loadAndOpenChat(graphId.value, props.id);
};
</script>

<template>
    <NodeResizer
        :isVisible="true"
        :minWidth="blockDefinition?.minSize?.width"
        :minHeight="minHeight"
        color="transparent"
    ></NodeResizer>

    <div
        class="bg-terracotta-clay border-terracotta-clay-dark relative flex h-full w-full flex-col rounded-3xl
            border-2 p-4 pt-3 text-black shadow-lg transition-all duration-200 ease-in-out"
        :class="{ 'opacity-50': props.dragging }"
    >
        <!-- Block Header -->
        <div class="mb-2 flex w-full items-center justify-between">
            <label
                class="text-soft-silk/80 mb-2 flex w-fit items-center gap-2 text-lg font-bold"
                :for="'prompt-textarea-' + props.id"
                v-if="blockDefinition"
            >
                <UiIcon class="text-soft-silk h-6 w-6 opacity-80" :name="blockDefinition.icon" />
                {{ blockDefinition?.name }}
            </label>

            <div class="flex items-center space-x-2">
                <!-- Open Chat Button -->
                <button
                    class="hover:bg-obsidian/25 flex items-center justify-center rounded-lg p-1 transition-colors duration-200
                        ease-in-out"
                    @click="openChat"
                >
                    <UiIcon name="MaterialSymbolsAndroidChat" class="text-soft-silk h-5 w-5" />
                </button>

                <!-- More Action Button -->
                <UiGraphNodeUtilsActions
                    @update:deleteNode="emit('update:deleteNode', props.id)"
                ></UiGraphNodeUtilsActions>
            </div>
        </div>

        <!-- Block Content -->
        <div class="relative mb-5 flex h-fit w-fit flex-wrap justify-between gap-2">
            <div
                v-for="(model, index) in props.data.models"
                :key="index"
                class="bg-terracotta-clay-dark h-40 w-[19rem] shrink-0 rounded-2xl"
            >
                <UiModelsSelect
                    :model="model.model"
                    :setModel="
                        (model: string) => {
                            props.data.models[index].model = model;
                        }
                    "
                    variant="terracotta"
                    class="h-8 w-full"
                ></UiModelsSelect>

                <UiGraphNodeUtilsTextarea
                    :reply="model.reply"
                    :readonly="true"
                    :placeholder="`Model #${index + 1} response will appear here...`"
                    :autoscroll="true"
                    style="height: 8rem"
                ></UiGraphNodeUtilsTextarea>
            </div>
        </div>

        <div class="mb-2 flex h-fit gap-4">
            <button
                class="bg-obsidian/25 hover:bg-obsidian/40 flex h-8 w-8 flex-shrink-0 cursor-pointer items-center
                    justify-center rounded-2xl transition-colors duration-200 ease-in-out disabled:cursor-not-allowed
                    disabled:opacity-50"
                @click="addParallelizationModel"
                :disabled="isStreaming"
                :aria-disabled="isStreaming"
            >
                <UiIcon name="Fa6SolidPlus" class="text-soft-silk h-4 w-4" />
            </button>

            <div class="bg-obsidian/25 flex items-center rounded-2xl">
                <span class="text-soft-silk px-4 text-sm font-bold">Aggregator</span>
                <UiModelsSelect
                    :model="props.data.aggregator.model"
                    :setModel="
                        (model: string) => {
                            props.data.aggregator.model = model;
                        }
                    "
                    variant="terracotta"
                    class="h-8 w-full"
                ></UiModelsSelect>
            </div>

            <!-- Send Prompt -->
            <button
                class="nodrag bg-obsidian/25 hover:bg-obsidian/40 relative flex h-8 w-8 cursor-pointer items-center
                    justify-center rounded-2xl transition-colors duration-200 ease-in-out disabled:cursor-not-allowed
                    disabled:opacity-50"
                @click="sendPrompt"
                :disabled="isStreaming"
            >
                <UiIcon
                    name="IconamoonSendFill"
                    class="text-soft-silk h-5 w-5 opacity-80"
                    v-if="!isStreaming"
                />
                <UiIcon v-else name="LineMdLoadingTwotoneLoop" class="text-soft-silk h-7 w-7" />

                <span
                    class="bg-soft-silk text-terracotta-clay-dark absolute top-0 right-0 h-3 w-3 rounded-full text-[0.5rem]
                        font-bold"
                >
                    {{ props.data.models.length }}
                </span>
            </button>
        </div>

        <UiGraphNodeUtilsTextarea
            :reply="props.data.aggregator.reply"
            :readonly="true"
            color="terracotta-clay"
            placeholder="Aggregator response will appear here..."
            :autoscroll="true"
            style="height: 10rem"
        ></UiGraphNodeUtilsTextarea>
    </div>

    <Handle
        type="target"
        :position="Position.Top"
        :id="'prompt_' + props.id"
        :connectable="handleConnectableInputPrompt"
        style="left: 33%; background: #b2c7db"
        class="handletop"
    />
    <Handle
        type="target"
        :position="Position.Top"
        :id="'context_' + props.id"
        :connectable="handleConnectableInputContext"
        style="left: 66%; background: #e5ca5b"
        class="handletop"
    />
    <UiGraphNodeUtilsHandleWheel
        v-if="isReady"
        :nodeId="props.id"
        :options="AVAILABLE_WHEELS.filter((wheel) => blockSettings.wheel.includes(wheel.value))"
    ></UiGraphNodeUtilsHandleWheel>
</template>

<style scoped></style>
