<script setup lang="ts">
import type { PromptImproverClarificationRound } from '@/types/promptImprover';
import type { ToolQuestionAnswerMap } from '@/types/toolCall';

import ToolQuestionCardBase from '@/components/ui/utils/toolQuestionCardBase.vue';

defineProps<{
    round: PromptImproverClarificationRound;
    isSubmitting?: boolean;
    remoteError?: string;
}>();

const emit = defineEmits<{
    submit: [answer: ToolQuestionAnswerMap];
}>();
</script>

<template>
    <ToolQuestionCardBase
        :detail="round"
        :is-submitting="isSubmitting"
        :remote-error="remoteError"
        @submit="emit('submit', $event)"
    />
</template>
