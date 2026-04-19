<script setup lang="ts">
import { MessageContentTypeEnum, MessageRoleEnum, NodeTypeEnum } from '@/types/enums';
import type { ToolCallDetail, ToolQuestionAnswerMap } from '@/types/toolCall';

import ToolQuestionCardBase from '@/components/ui/utils/toolQuestionCardBase.vue';

const props = defineProps<{
    toolCallId: string;
}>();

const { sendMessage } = useWebSocket();
const chatStore = useChatStore();
const streamStore = useStreamStore();
const { openChatId } = storeToRefs(chatStore);
const { toolQuestionErrors } = storeToRefs(streamStore);
const { fetchToolCallDetail } = useToolCallDetails();

const detail = ref<ToolCallDetail | null>(null);
const isLoading = ref(true);
const isSubmitting = ref(false);
const draftAnswers = ref<ToolQuestionAnswerMap>({});
const draftStepIndex = ref(0);
let refreshTimer: number | null = null;

const TOOL_QUESTION_DRAFT_STORAGE_KEY_PREFIX = 'meridian-tool-question-draft';

type ToolQuestionDraftStorage = {
    answers: ToolQuestionAnswerMap;
    stepIndex: number;
};

const getDraftStorageKey = () => `${TOOL_QUESTION_DRAFT_STORAGE_KEY_PREFIX}:${props.toolCallId}`;

const getEmptyDraftStorage = (): ToolQuestionDraftStorage => ({
    answers: {},
    stepIndex: 0,
});

const loadDraftStorage = (): ToolQuestionDraftStorage => {
    if (!import.meta.client) {
        return getEmptyDraftStorage();
    }

    try {
        const storedDraft = localStorage.getItem(getDraftStorageKey());
        if (!storedDraft) {
            return getEmptyDraftStorage();
        }

        const parsed = JSON.parse(storedDraft);
        if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
            return getEmptyDraftStorage();
        }

        const answers =
            parsed.answers && typeof parsed.answers === 'object' && !Array.isArray(parsed.answers)
                ? (parsed.answers as ToolQuestionAnswerMap)
                : {};
        const stepIndex = typeof parsed.stepIndex === 'number' ? parsed.stepIndex : 0;

        return {
            answers,
            stepIndex,
        };
    } catch (error) {
        console.error('Failed to load tool question draft', error);
        return getEmptyDraftStorage();
    }
};

const persistDraftStorage = () => {
    if (!import.meta.client) {
        return;
    }

    try {
        if (Object.keys(draftAnswers.value).length === 0 && draftStepIndex.value === 0) {
            localStorage.removeItem(getDraftStorageKey());
            return;
        }

        localStorage.setItem(
            getDraftStorageKey(),
            JSON.stringify({
                answers: draftAnswers.value,
                stepIndex: draftStepIndex.value,
            }),
        );
    } catch (error) {
        console.error('Failed to save tool question draft', error);
    }
};

const clearDraftAnswers = () => {
    draftAnswers.value = {};
    draftStepIndex.value = 0;

    if (!import.meta.client) {
        return;
    }

    try {
        localStorage.removeItem(getDraftStorageKey());
    } catch (error) {
        console.error('Failed to clear tool question draft', error);
    }
};

const handleDraftChange = (answers: ToolQuestionAnswerMap) => {
    draftAnswers.value = answers;
    persistDraftStorage();
};

const handleDraftStepChange = (stepIndex: number) => {
    draftStepIndex.value = stepIndex;
    persistDraftStorage();
};

const remoteError = computed(() => toolQuestionErrors.value.get(props.toolCallId) || '');

const appendToActiveAssistantMessage = (chunk: string, modelId: string | undefined) => {
    if (modelId || !detail.value?.node_id || openChatId.value !== detail.value.node_id) {
        return;
    }

    const chatSession = chatStore.getSession(detail.value.node_id);
    const lastMessage = chatSession.messages[chatSession.messages.length - 1];
    if (!lastMessage || lastMessage.role !== MessageRoleEnum.assistant) {
        return;
    }

    const textContent = lastMessage.content.find(
        (content) => content.type === MessageContentTypeEnum.TEXT,
    );
    if (textContent) {
        textContent.text = `${textContent.text || ''}${chunk}`;
        return;
    }

    lastMessage.content.unshift({
        type: MessageContentTypeEnum.TEXT,
        text: chunk,
    });
};

const getResumeNodeType = (): NodeTypeEnum => {
    if (!detail.value?.node_id) {
        return NodeTypeEnum.TEXT_TO_TEXT;
    }

    const chatSession = chatStore.getSession(detail.value.node_id);
    const lastMessage = chatSession.messages[chatSession.messages.length - 1];
    return lastMessage?.type || NodeTypeEnum.TEXT_TO_TEXT;
};

const prepareStreamResume = (nodeId: string) => {
    const nodeType = getResumeNodeType();
    streamStore.ensureSession(nodeId, nodeType);
    streamStore.setChatCallback(nodeId, nodeType, appendToActiveAssistantMessage);
    streamStore.resumeExistingStream(nodeId);
};

const loadDetail = async (forceRefresh: boolean = false) => {
    isLoading.value = true;
    try {
        detail.value = await fetchToolCallDetail(props.toolCallId, forceRefresh);
        if (detail.value?.status === 'pending_user_input') {
            const draftStorage = loadDraftStorage();
            draftAnswers.value = draftStorage.answers;
            draftStepIndex.value = draftStorage.stepIndex;
            return;
        }

        clearDraftAnswers();
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

    prepareStreamResume(detail.value.node_id);
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
            clearDraftAnswers();
        }
    },
);

onMounted(() => {
    const draftStorage = loadDraftStorage();
    draftAnswers.value = draftStorage.answers;
    draftStepIndex.value = draftStorage.stepIndex;
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
            :draft-answers="draftAnswers"
            :draft-step-index="draftStepIndex"
            :is-submitting="isSubmitting"
            :remote-error="remoteError"
            class="my-3"
            @draft-change="handleDraftChange"
            @draft-step-change="handleDraftStepChange"
            @submit="submitAnswer"
        />
    </div>
</template>

<style scoped></style>
