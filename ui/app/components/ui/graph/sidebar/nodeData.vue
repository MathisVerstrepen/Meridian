<script lang="ts" setup>
import { NodeTypeEnum, SavingStatus } from '@/types/enums';
import {
    useVueFlow,
} from '@vue-flow/core';
import type {
    DataContextMerger,
    DataParallelization,
    DataPrompt,
    DataRouting,
    DataTextToText,
    SidebarNode,
} from '@/types/graph';

const props = defineProps<{
    nodeId: string | null;
    graphId: string | null;
}>();

// --- Stores ---
const canvasSaveStore = useCanvasSaveStore();
const chatStore = useChatStore();

// --- State from Stores (Reactive Refs) ---
const { upcomingModelData, openChatId } = storeToRefs(chatStore);

// --- Actions/Methods from Stores ---
const { setNeedSave } = canvasSaveStore;
const { getSession, updateUpcomingModelData } = chatStore;

// --- Composables ---
const { getNodes } = useVueFlow('main-graph-' + props.graphId);
const { getBlockById } = useBlocks();

// --- Local State ---
type SidebarEditableData = object;

type SidebarEditableNode = SidebarNode<SidebarEditableData>;

const node = ref<SidebarEditableNode | null>(null);

// --- Computed ---
const session = computed(() => {
    return getSession(openChatId.value);
});

const lastAssistantMessage = computed(() => {
    if (!session.value?.messages) return null;
    const assistantMessages = session.value.messages.filter(
        (m) => m.role === 'assistant' && m.node_id,
    );
    return assistantMessages.length > 0 ? assistantMessages[assistantMessages.length - 1] : null;
});

const lastAssistantNode = computed<SidebarEditableNode | null>(() => {
    if (!lastAssistantMessage.value) return null;
    return getNodes.value.find((n) => n.id === lastAssistantMessage.value.node_id) ?? null;
});

const isEditingUpcomingNode = computed(() => !props.nodeId && !!openChatId.value);

const displayNode = computed<SidebarEditableNode | null>(() => {
    if (isEditingUpcomingNode.value) {
        return {
            id: 'upcoming-node',
            label: 'Upcoming Node',
            type: upcomingModelData.value.type,
            data: isRuntimeObject(upcomingModelData.value.data) ? upcomingModelData.value.data : {},
            position: { x: 0, y: 0 },
        };
    }
    return node.value;
});

const navigatorNode = computed<SidebarEditableNode | null>(() => {
    if (isEditingUpcomingNode.value) {
        return lastAssistantNode.value;
    }
    return displayNode.value;
});

const promptNode = computed<SidebarNode<DataPrompt> | null>(() =>
    displayNode.value ? (/* SAFETY: Block registry pairs PROMPT nodes with DataPrompt; Vue Flow's base node type erases that data mapping. */ displayNode.value as SidebarNode<DataPrompt>) : null,
);

const textToTextNode = computed<SidebarNode<DataTextToText> | null>(() =>
    displayNode.value ? (/* SAFETY: Block registry pairs TEXT_TO_TEXT nodes with DataTextToText; Vue Flow's base node type erases that data mapping. */ displayNode.value as SidebarNode<DataTextToText>) : null,
);

const parallelizationNode = computed<SidebarNode<DataParallelization> | null>(() =>
    displayNode.value
        ? (/* SAFETY: Block registry pairs PARALLELIZATION nodes with DataParallelization; Vue Flow's base node type erases that data mapping. */ displayNode.value as SidebarNode<DataParallelization>)
        : null,
);

const routingNode = computed<SidebarNode<DataRouting> | null>(() =>
    displayNode.value ? (/* SAFETY: Block registry pairs ROUTING nodes with DataRouting; Vue Flow's base node type erases that data mapping. */ displayNode.value as SidebarNode<DataRouting>) : null,
);

const contextMergerNode = computed<SidebarNode<DataContextMerger> | null>(() =>
    displayNode.value ? (/* SAFETY: Block registry pairs CONTEXT_MERGER nodes with DataContextMerger; Vue Flow's base node type erases that data mapping. */ displayNode.value as SidebarNode<DataContextMerger>) : null,
);

// --- Core logic ---
const setNodeDataKey = (key: string, value: JsonValue) => {
    const target = isEditingUpcomingNode.value ? upcomingModelData.value : node.value;
    if (!target) return;

    const dataObject = isEditingUpcomingNode.value
        ? upcomingModelData.value.data
        : node.value?.data;
    if (!dataObject) return;

    const keys = key.split('.');
    const current = isJsonObject(dataObject) ? dataObject : {};

    current[keys[keys.length - 1]] = value;

    // Trigger reactivity
    if (isEditingUpcomingNode.value) {
        updateUpcomingModelData(upcomingModelData.value.type, current);
    } else {
        const currentNode = node.value;
        if (!currentNode) return;
        currentNode.data = { ...current };
        setNeedSave(SavingStatus.NOT_SAVED);
    }
};

const setCurrentModel = (model: string) => {
    if (isEditingUpcomingNode.value && isJsonObject(upcomingModelData.value.data)) {
        upcomingModelData.value.data.model = model;
    }
};

const handleUpdateUpcomingType = (newType: NodeTypeEnum) => {
    let defaultData: object | undefined;

    if (lastAssistantMessage.value && newType === lastAssistantMessage.value.type) {
        const node = getNodes.value.find((n) => n.id === lastAssistantMessage.value!.node_id);

        if (node) {
            defaultData = node.data;
        }
    }

    if (!defaultData) {
        switch (newType) {
            case NodeTypeEnum.ROUTING:
                defaultData = getBlockById('primary-model-routing').defaultData;
                break;
            case NodeTypeEnum.PARALLELIZATION:
                defaultData = getBlockById('primary-model-parallelization').defaultData;
                break;
            case NodeTypeEnum.TEXT_TO_TEXT:
            default:
                defaultData = getBlockById('primary-model-text-to-text').defaultData;
                break;
        }
    }

    if (defaultData) updateUpcomingModelData(newType, defaultData);
};

// --- Watchers ---
watch(
    () => props.nodeId,
    (newVal) => {
        if (newVal) {
            node.value = getNodes.value.find((n) => n.id === newVal) ?? null;
        } else {
            node.value = null;
        }
    },
    { immediate: true },
);
</script>

<template>
    <div class="h-full w-full px-4">
        <Transition name="fade" mode="out-in">
            <div v-if="displayNode" class="flex h-full flex-col space-y-6">
                <!-- Metadata Section -->
                <UiGraphSidebarNodeDataMetadata :node="displayNode" />

                <!-- Upcoming Node Type Selector -->
                <UiGraphSidebarNodeDataUpcomingTypeSelector
                    v-if="isEditingUpcomingNode"
                    :model-value="upcomingModelData.type || NodeTypeEnum.TEXT_TO_TEXT"
                    @update:model-value="handleUpdateUpcomingType"
                />

                <!-- Prompt Node Settings -->
                <UiGraphSidebarNodeDataPrompt
                    v-if="displayNode.type === NodeTypeEnum.PROMPT && promptNode"
                    :node="promptNode"
                    :graph-id="graphId"
                    :set-node-data-key="setNodeDataKey"
                />

                <!-- Text to Text Node Settings -->
                <UiGraphSidebarNodeDataTextToText
                    v-else-if="displayNode.type === NodeTypeEnum.TEXT_TO_TEXT && textToTextNode"
                    :node="textToTextNode"
                    :set-node-data-key="setNodeDataKey"
                    :set-current-model="setCurrentModel"
                />

                <!-- Parallelization Node Settings -->
                <UiGraphSidebarNodeDataParallelization
                    v-else-if="
                        displayNode.type === NodeTypeEnum.PARALLELIZATION && parallelizationNode
                    "
                    :node="parallelizationNode"
                    :set-node-data-key="setNodeDataKey"
                    :set-current-model="setCurrentModel"
                />

                <!-- Routing Node Settings -->
                <UiGraphSidebarNodeDataRouting
                    v-else-if="displayNode.type === NodeTypeEnum.ROUTING && routingNode"
                    :node="routingNode"
                    :set-node-data-key="setNodeDataKey"
                />

                <UiGraphSidebarNodeDataContextMerger
                    v-else-if="displayNode.type === NodeTypeEnum.CONTEXT_MERGER && contextMergerNode"
                    :node="contextMergerNode"
                    :set-node-data-key="setNodeDataKey"
                />

                <!-- Navigator (only for existing nodes) -->
                <UiGraphSidebarNodeDataMessageNavigator
                    v-if="openChatId && navigatorNode"
                    :session="session"
                    :node="navigatorNode"
                    :is-editing-upcoming-node="isEditingUpcomingNode"
                    class="mt-auto mb-0"
                />
            </div>

            <!-- Empty State -->
            <div
                v-else
                class="flex h-full w-full flex-col items-center justify-center space-y-2
                    text-center"
            >
                <UiIcon name="MajesticonsInformationCircleLine" class="text-stone-gray h-7 w-7" />
                <p class="text-stone-gray text-sm">Select a node to view its properties.</p>
            </div>
        </Transition>
    </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
    transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
    opacity: 0;
}
</style>
