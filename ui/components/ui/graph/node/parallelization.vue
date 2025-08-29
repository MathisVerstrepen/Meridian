<script lang="ts" setup>
import { type NodeProps } from '@vue-flow/core';
import { NodeResizer } from '@vue-flow/node-resizer';

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
const { blockSettings } = storeToRefs(globalSettingsStore);

// --- Actions/Methods from Stores ---
const { ensureGraphSaved, saveGraph } = canvasSaveStore;
const { startStream, setCanvasCallback, preStreamSession, removeChatCallback, cancelStream } =
    streamStore;
const { loadAndOpenChat } = chatStore;

// --- Composables ---
const { getGenerateParallelizationAggregatorStream } = useAPI();
const { addChunkCallbackBuilder, addChunkCallbackBuilderWithId } = useStreamCallbacks();
const { getBlockById } = useBlocks();
const { generateId } = useUniqueId();
const nodeRegistry = useNodeRegistry();

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
    (chunk: string) => {
        if (props.data) props.data.aggregator.reply += chunk;
    },
);

const sendAggregator = async () => {
    if (!isStreaming.value) return;

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

const sendPrompt = async () => {
    if (!props.data) return;

    isStreaming.value = true;
    doneModels.value = 0;
    props.data.aggregator.reply = '';

    await ensureGraphSaved();

    let jobs: Promise<StreamSession | undefined>[] = [];

    preStreamSession(props.id, NodeTypeEnum.PARALLELIZATION, false);

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
                modelId: model.id,
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

    await sendAggregator();
};

const sendPromptOneModel = async (index: number) => {
    if (!props.data || index < 0 || index >= props.data.models.length) return;

    isStreaming.value = true;
    props.data.aggregator.reply = '';

    const model = props.data.models[index];
    model.reply = '';

    setCanvasCallback(model.id, NodeTypeEnum.TEXT_TO_TEXT, async (chunk: string) => {
        addChunkModels(chunk, model.id);
    });

    await startStream(
        model.id,
        NodeTypeEnum.TEXT_TO_TEXT,
        {
            graph_id: graphId.value,
            node_id: props.id,
            model: model.model,
        },
        false,
    );

    isStreaming.value = false;
};

const openChat = async () => {
    currentModel.value = props.data.aggregator.model;
    loadAndOpenChat(graphId.value, props.id);
};

const handleCancelStream = async () => {
    if (!props.data) return;
    removeChatCallback(props.id, NodeTypeEnum.TEXT_TO_TEXT);
    await nextTick();
    props.data.aggregator.reply = '';
    props.data.models.forEach(async (model) => {
        removeChatCallback(model.id, NodeTypeEnum.TEXT_TO_TEXT);
    });
    await nextTick();
    props.data.models.forEach(async (model) => {
        model.reply = '';
    });
    doneModels.value = 0;
    isStreaming.value = false;
    await cancelStream(props.id);
};

// --- Lifecycle Hooks ---
onMounted(() => {
    nodeRegistry.register(props.id, sendPrompt, handleCancelStream);
});

onUnmounted(() => {
    nodeRegistry.unregister(props.id);
});
</script>

<template>
    <NodeResizer
        :isVisible="true"
        :minWidth="blockDefinition?.minSize?.width"
        :minHeight="minHeight"
        color="transparent"
        :nodeId="props.id"
    ></NodeResizer>

    <UiGraphNodeUtilsRunToolbar
        :graphId="graphId"
        :nodeId="props.id"
        :selected="props.selected"
        source="generator"
        @update:deleteNode="emit('update:deleteNode', props.id)"
    ></UiGraphNodeUtilsRunToolbar>

    <div
        class="bg-terracotta-clay border-terracotta-clay-dark relative flex h-full w-full flex-col rounded-3xl
            border-2 p-4 pt-3 text-black shadow-lg transition-all duration-200 ease-in-out"
        :class="{
            'opacity-50': props.dragging,
            'animate-pulse': isStreaming,
            'shadow-terracotta-clay-dark !shadow-[0px_0px_15px_3px]': props.selected,
        }"
        @dblclick="openChat"
    >
        <!-- Block Header -->
        <div class="mb-2 flex w-full items-center justify-between">
            <label
                class="dark:text-soft-silk/80 text-anthracite mb-2 flex w-fit items-center gap-2 text-lg font-bold"
                :for="'prompt-textarea-' + props.id"
                v-if="blockDefinition"
            >
                <UiIcon
                    class="dark:text-soft-silk text-anthracite h-6 w-6 opacity-80"
                    :name="blockDefinition.icon"
                />
                {{ blockDefinition?.name }}
            </label>

            <div class="flex items-center space-x-2">
                <!-- Open Chat Button -->
                <button
                    class="hover:bg-obsidian/25 flex items-center justify-center rounded-lg p-1 transition-colors duration-200
                        ease-in-out"
                    @click="openChat"
                >
                    <UiIcon
                        name="MaterialSymbolsAndroidChat"
                        class="dark:text-soft-silk text-anthracite h-5 w-5"
                    />
                </button>
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
                    :disabled="false"
                    variant="terracotta"
                    class="h-8 w-full"
                ></UiModelsSelect>

                <div class="group relative">
                    <UiGraphNodeUtilsTextarea
                        :reply="model.reply"
                        :readonly="true"
                        :placeholder="`Model #${index + 1} response will appear here...`"
                        :autoscroll="true"
                        style="height: 8rem"
                    ></UiGraphNodeUtilsTextarea>
                    <div
                        class="absolute top-0 right-0 flex flex-col items-center justify-between gap-1 p-2 opacity-0
                            transition-opacity duration-200 ease-in-out group-hover:opacity-100"
                    >
                        <button
                            v-if="!isStreaming"
                            class="bg-stone-gray/30 hover:bg-stone-gray/80 dark:text-soft-silk text-anthracite flex h-5 w-5
                                cursor-pointer items-center justify-center rounded-full p-1 backdrop-blur transition-colors
                                duration-200 ease-in-out"
                            title="Remove Model"
                            @click="props.data.models.splice(index, 1)"
                        >
                            <UiIcon
                                name="MaterialSymbolsDeleteRounded"
                                class="text-terracotta-clay-dark h-3 w-3"
                            />
                        </button>
                        <button
                            v-if="!isStreaming"
                            class="bg-stone-gray/30 hover:bg-stone-gray/80 dark:text-soft-silk text-anthracite flex h-5 w-5
                                cursor-pointer items-center justify-center rounded-full p-1 backdrop-blur transition-colors
                                duration-200 ease-in-out"
                            title="Run this model only"
                            @click="sendPromptOneModel(index)"
                        >
                            <UiIcon
                                name="IconamoonSendFill"
                                class="text-terracotta-clay-dark h-3 w-3"
                            />
                        </button>
                    </div>
                </div>
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
                <UiIcon name="Fa6SolidPlus" class="dark:text-soft-silk text-anthracite h-4 w-4" />
            </button>

            <div class="bg-obsidian/25 flex items-center rounded-2xl">
                <span class="dark:text-soft-silk text-anthracite px-4 text-sm font-bold"
                    >Aggregator</span
                >
                <UiModelsSelect
                    :model="props.data.aggregator.model"
                    :setModel="
                        (model: string) => {
                            props.data.aggregator.model = model;
                        }
                    "
                    :disabled="false"
                    variant="terracotta"
                    class="h-8 w-full"
                ></UiModelsSelect>
            </div>

            <!-- Send Prompt -->
            <button
                v-if="!isStreaming"
                @click="sendPrompt"
                :disabled="!props.data?.aggregator.model || props.data.models.length === 0"
                class="nodrag bg-obsidian/25 hover:bg-obsidian/40 relative flex h-8 w-8 cursor-pointer items-center
                    justify-center rounded-2xl transition-colors duration-200 ease-in-out disabled:cursor-not-allowed
                    disabled:opacity-50"
            >
                <UiIcon
                    name="IconamoonSendFill"
                    class="dark:text-soft-silk text-anthracite h-5 w-5 opacity-80"
                />

                <span
                    class="dark:bg-soft-silk bg-soft-silk/20 dark:text-terracotta-clay-dark text-anthracite absolute top-0
                        right-0 h-3 w-3 rounded-full text-[0.5rem] font-bold backdrop-blur-lg"
                >
                    {{ props.data.models.length }}
                </span>
            </button>

            <button
                v-else
                @click="handleCancelStream"
                :disabled="!props.data?.aggregator.model"
                class="nodrag bg-obsidian/25 hover:bg-obsidian/40 dark:text-soft-silk text-anthracite relative flex h-8 w-8
                    flex-shrink-0 cursor-pointer items-center justify-center rounded-2xl transition-all duration-200
                    ease-in-out disabled:cursor-not-allowed disabled:opacity-50"
            >
                <UiIcon name="MaterialSymbolsStopRounded" class="h-5 w-5" />
            </button>
        </div>

        <div class="group relative h-full">
            <UiGraphNodeUtilsTextarea
                :reply="props.data.aggregator.reply"
                :readonly="true"
                color="terracotta-clay"
                placeholder="Aggregator response will appear here..."
                :autoscroll="true"
                style="height: 100%"
            ></UiGraphNodeUtilsTextarea>
            <div
                class="absolute top-0 right-0 flex flex-col items-center justify-between gap-1 p-2 opacity-0
                    transition-opacity duration-200 ease-in-out group-hover:opacity-100"
            >
                <button
                    v-if="!isStreaming"
                    class="bg-stone-gray/30 hover:bg-stone-gray/80 flex h-5 w-5 cursor-pointer items-center justify-center
                        rounded-full p-1 text-white backdrop-blur transition-colors duration-200 ease-in-out"
                    title="Run aggregator only"
                    @click="
                        () => {
                            isStreaming = true;
                            sendAggregator();
                        }
                    "
                >
                    <UiIcon name="IconamoonSendFill" class="text-terracotta-clay-dark h-3 w-3" />
                </button>
            </div>
        </div>
    </div>

    <UiGraphNodeUtilsHandlePrompt
        type="target"
        :style="{ left: '33%' }"
        :id="props.id"
        :isDragging="props.dragging"
    />
    <UiGraphNodeUtilsHandleContext
        type="target"
        :id="props.id"
        :nodeId="props.id"
        :options="[]"
        :style="{ left: '66%' }"
        :isDragging="props.dragging"
    ></UiGraphNodeUtilsHandleContext>
    <UiGraphNodeUtilsHandleAttachment type="target" :id="props.id" :isDragging="props.dragging" />
    <UiGraphNodeUtilsHandleContext
        :nodeId="props.id"
        :options="blockSettings.contextWheel"
        type="source"
        :id="props.id"
        :isDragging="props.dragging"
    ></UiGraphNodeUtilsHandleContext>
</template>

<style scoped></style>
