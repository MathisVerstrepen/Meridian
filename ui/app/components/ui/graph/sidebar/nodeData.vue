<script lang="ts" setup>
import { useVueFlow, type Node } from '@vue-flow/core';
import { NodeTypeEnum, SavingStatus } from '@/types/enums';

const props = defineProps<{
    nodeId: string | null;
    graphId: string | null;
}>();

// --- Stores ---
const canvasSaveStore = useCanvasSaveStore();
const chatStore = useChatStore();

// --- State from Stores (Reactive Refs) ---
const { currentModel, openChatId } = storeToRefs(chatStore);

// --- Actions/Methods from Stores ---
const { setNeedSave } = canvasSaveStore;
const { getSession } = chatStore;

// --- Composables ---
const { getNodes } = useVueFlow('main-graph-' + props.graphId);

// --- Computed ---
const session = computed(() => {
    return getSession(openChatId.value);
});

// --- Local State ---
const node = ref<Node | null>(null);

// --- Core logic ---
const setNodeDataKey = (key: string, value: unknown) => {
    if (!node.value) return;

    const keys = key.split('.');
    let current = node.value.data || {};

    for (let i = 0; i < keys.length - 1; i++) {
        const part = keys[i];
        if (!current[part] || typeof current[part] !== 'object') {
            current[part] = {};
        }
        current = current[part];
    }

    current[keys[keys.length - 1]] = value;

    // Trigger reactivity
    node.value.data = { ...node.value.data };

    setNeedSave(SavingStatus.NOT_SAVED);
};

// --- Watchers ---
watch(
    () => props.nodeId,
    (newVal) => {
        if (newVal) {
            node.value = getNodes.value.find((n) => n.id === newVal) || null;
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
            <div v-if="node" class="flex h-full flex-col space-y-6">
                <!-- Metadata Section -->
                <UiGraphSidebarNodeDataMetadata :node="node" />

                <!-- Prompt Node Settings -->
                <UiGraphSidebarNodeDataPrompt
                    v-if="node.type === NodeTypeEnum.PROMPT"
                    :node="node"
                    :graph-id="graphId"
                    :set-node-data-key="setNodeDataKey"
                />

                <!-- Text to Text Node Settings -->
                <UiGraphSidebarNodeDataTextToText
                    v-else-if="node.type === NodeTypeEnum.TEXT_TO_TEXT"
                    :node="node"
                    :set-node-data-key="setNodeDataKey"
                    :set-current-model="
                        (model: string) => {
                            currentModel = model;
                        }
                    "
                />

                <!-- Parallelization Node Settings -->
                <UiGraphSidebarNodeDataParallelization
                    v-else-if="node.type === NodeTypeEnum.PARALLELIZATION"
                    :node="node"
                    :set-node-data-key="setNodeDataKey"
                    :set-current-model="
                        (model: string) => {
                            currentModel = model;
                        }
                    "
                />

                <!-- Routing Node Settings -->
                <UiGraphSidebarNodeDataRouting
                    v-else-if="node.type === NodeTypeEnum.ROUTING"
                    :node="node"
                    :set-node-data-key="setNodeDataKey"
                />

                <UiGraphSidebarNodeDataMessageNavigator
                    v-if="openChatId"
                    :session="session"
                    :node="node"
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
