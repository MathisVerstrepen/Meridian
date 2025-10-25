<script lang="ts" setup>
import type { ChatSession } from '@/types/chat';
import type { Node } from '@vue-flow/core';

const props = defineProps<{
    session: ChatSession;
    node: Node;
    isEditingUpcomingNode?: boolean;
}>();

// --- Composables ---
const graphEvents = useGraphEvents();

// --- Computed ---
const assistantNodes = computed(() => props.session.messages.filter((n) => n.role === 'assistant'));

const currentIndex = computed(() =>
    assistantNodes.value.findIndex((n) => n.node_id === props.node.id),
);

const previousNode = computed(() => {
    if (props.isEditingUpcomingNode) {
        return assistantNodes.value[assistantNodes.value.length - 1] || null;
    }
    if (currentIndex.value > 0) {
        return assistantNodes.value[currentIndex.value - 1];
    }
    return null;
});

const nextNode = computed(() => {
    if (currentIndex.value < assistantNodes.value.length - 1) {
        return assistantNodes.value[currentIndex.value + 1];
    }
    return null;
});

// --- Core logic ---
const selectPreviousAssistantNode = () => {
    if (previousNode.value) {
        graphEvents.emit('open-node-data', {
            selectedNodeId: previousNode.value.node_id || null,
        });
    }
};

const selectNextAssistantNode = () => {
    if (nextNode.value) {
        graphEvents.emit('open-node-data', {
            selectedNodeId: nextNode.value.node_id || null,
        });
    } else {
        graphEvents.emit('open-upcoming-node-data', {});
    }
};

// --- Lifecycle ---
watch(
    () => ({ nodeId: props.node.id, isUpcoming: props.isEditingUpcomingNode }),
    (newVal) => {
        if (newVal.isUpcoming) {
            graphEvents.emit('highlight-node', { nodeId: null });
        } else {
            graphEvents.emit('highlight-node', { nodeId: newVal.nodeId });
        }
    },
    { immediate: true },
);

onUnmounted(() => {
    graphEvents.emit('highlight-node', { nodeId: null });
});
</script>

<template>
    <div class="flex justify-between">
        <button
            class="text-stone-gray flex cursor-pointer items-center gap-1 px-1 py-1 text-sm
                select-none hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="!previousNode"
            @click="selectPreviousAssistantNode"
        >
            <UiIcon name="FlowbiteChevronDownOutline" class="h-5 w-5 rotate-90" />
            Previous
        </button>
        <button
            v-if="!isEditingUpcomingNode"
            class="text-stone-gray flex cursor-pointer items-center gap-1 px-1 py-1 text-sm
                select-none hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
            @click="selectNextAssistantNode"
        >
            {{ nextNode ? 'Next' : 'Upcoming Node' }}
            <UiIcon name="FlowbiteChevronDownOutline" class="h-5 w-5 -rotate-90" />
        </button>
    </div>
</template>

<style scoped></style>
