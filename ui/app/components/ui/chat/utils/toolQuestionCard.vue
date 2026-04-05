<script setup lang="ts">
import type { ToolCallDetail, ToolQuestionAnswerMap } from '@/types/toolCall';

import ToolQuestionCardBase from '@/components/ui/utils/toolQuestionCardBase.vue';

const props = defineProps<{
    toolCallId: string;
}>();

const { sendMessage } = useWebSocket();
const streamStore = useStreamStore();
const { toolQuestionErrors } = storeToRefs(streamStore);
const { fetchToolCallDetail } = useToolCallDetails();

const detail = ref<ToolCallDetail | null>(null);
const isLoading = ref(true);
const isSubmitting = ref(false);
let refreshTimer: number | null = null;

const remoteError = computed(() => toolQuestionErrors.value.get(props.toolCallId) || '');

const loadDetail = async (forceRefresh: boolean = false) => {
    isLoading.value = true;
    try {
        detail.value = await fetchToolCallDetail(props.toolCallId, forceRefresh);
    } finally {
        isLoading.value = false;
    }
};

const scheduleRefreshUntilAnswered = () => {
    if (refreshTimer !== null) {
        window.clearTimeout(refreshTimer);
    }

    let attempts = 0;
    const tick = async () => {
        attempts += 1;
        await loadDetail(true);
        if (detail.value?.status === 'pending_user_input' && attempts < 12) {
            refreshTimer = window.setTimeout(() => {
                void tick();
            }, 400);
            return;
        }
        isSubmitting.value = false;
    };

    refreshTimer = window.setTimeout(() => {
        void tick();
    }, 250);
};

const submitAnswer = async (answer: ToolQuestionAnswerMap) => {
    streamStore.clearToolQuestionError(props.toolCallId);

    if (!detail.value?.node_id) {
        return;
    }

    streamStore.resumeExistingStream(detail.value.node_id);
    isSubmitting.value = true;
    sendMessage({
        type: 'submit_tool_response',
        payload: {
            tool_call_id: props.toolCallId,
            node_id: detail.value.node_id,
            answer,
        },
    });

    scheduleRefreshUntilAnswered();
};

watch(
    () => detail.value?.status,
    (status) => {
        if (status && status !== 'pending_user_input') {
            streamStore.clearToolQuestionError(props.toolCallId);
        }
    },
);

onMounted(() => {
    void loadDetail();
});

onBeforeUnmount(() => {
    if (refreshTimer !== null) {
        window.clearTimeout(refreshTimer);
    }
});
</script>

<template>
    <div data-testid="tool-question-card">
        <div v-if="isLoading" class="flex items-center gap-3 px-4 py-4">
            <div class="bg-stone-gray/15 h-4 w-4 animate-pulse rounded-full" />
            <div class="flex-1 space-y-2">
                <div class="bg-stone-gray/10 h-3 w-2/3 animate-pulse rounded" />
                <div class="bg-stone-gray/8 h-2.5 w-1/3 animate-pulse rounded" />
            </div>
        </div>

        <ToolQuestionCardBase
            v-else-if="detail"
            :detail="detail"
            :is-submitting="isSubmitting"
            :remote-error="remoteError"
            class="my-3"
            @submit="submitAnswer"
        />
    </div>
</template>

<style scoped></style>
