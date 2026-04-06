<script setup lang="ts">
import type { ToolCallDetail } from '@/types/toolCall';

const props = defineProps<{
    detail: ToolCallDetail;
}>();

interface QuestionItem {
    id: string;
    question: string;
    input_type: string;
    help_text?: string;
    options?: { label: string; value: string; subtext?: string }[];
}

interface AnswerItem {
    id: string;
    question: string;
    input_type: string;
    answer: Record<string, unknown>;
}

const args = computed(() => {
    const a = props.detail.arguments as Record<string, unknown>;
    return {
        title: a?.title ? String(a.title) : null,
        questions: Array.isArray(a?.questions) ? (a.questions as QuestionItem[]) : [],
    };
});

const result = computed(() => {
    const r = props.detail.result as Record<string, unknown>;
    return {
        title: r?.title ? String(r.title) : null,
        submitted_at: r?.submitted_at ? String(r.submitted_at) : null,
        answers: Array.isArray(r?.answers) ? (r.answers as AnswerItem[]) : [],
    };
});

const isPending = computed(() => props.detail.status === 'pending_user_input');

const answerMap = computed(() => {
    const map = new Map<string, AnswerItem>();
    for (const answer of result.value.answers) {
        if (answer.id) map.set(answer.id, answer);
    }
    return map;
});

const formatAnswer = (answer: Record<string, unknown>): string => {
    if (typeof answer.value === 'boolean') return answer.value ? 'Yes' : 'No';
    if (typeof answer.value === 'string') return answer.value;
    if (Array.isArray(answer.values)) return answer.values.join(', ');
    if (answer.label) return String(answer.label);
    if (Array.isArray(answer.labels)) return (answer.labels as string[]).join(', ');
    return JSON.stringify(answer);
};

const formatInputType = (type: string): string => {
    return type.replace(/_/g, ' ');
};

const formattedSubmittedAt = computed(() => {
    if (!result.value.submitted_at) return null;
    try {
        return new Date(result.value.submitted_at).toLocaleString();
    } catch {
        return result.value.submitted_at;
    }
});
</script>

<template>
    <div class="space-y-5">
        <!-- Title -->
        <p v-if="args.title || result.title" class="text-soft-silk text-[13px] font-semibold">
            {{ result.title || args.title }}
        </p>

        <!-- Pending indicator -->
        <div v-if="isPending" class="au-pending flex items-center gap-3 rounded-lg p-3.5">
            <span class="au-pending-dot" />
            <p class="text-[13px] text-amber-300/90">Awaiting user response</p>
        </div>

        <!-- Questions + Answers -->
        <div v-if="args.questions.length" class="space-y-3">
            <div
                v-for="(question, qi) in args.questions"
                :key="question.id"
                class="au-question rounded-lg p-4"
            >
                <!-- Question header -->
                <div class="mb-2 flex items-start gap-2.5">
                    <span class="text-stone-gray/40 mt-0.5 font-mono text-[11px]">
                        Q{{ qi + 1 }}
                    </span>
                    <div class="min-w-0 flex-1">
                        <p class="text-soft-silk text-[13px] leading-snug font-medium">
                            {{ question.question }}
                        </p>
                        <p
                            v-if="question.help_text"
                            class="text-stone-gray/50 mt-1 text-[12px] leading-relaxed"
                        >
                            {{ question.help_text }}
                        </p>
                    </div>
                    <span
                        class="bg-stone-gray/8 text-stone-gray/60 shrink-0 rounded-md px-2 py-0.5
                            text-[10px] capitalize"
                    >
                        {{ formatInputType(question.input_type) }}
                    </span>
                </div>

                <!-- Options -->
                <div v-if="question.options?.length" class="mb-3 ml-[26px] flex flex-wrap gap-1.5">
                    <span
                        v-for="option in question.options"
                        :key="option.value"
                        class="au-option rounded-md px-2 py-1 text-[11px]"
                    >
                        {{ option.label }}
                    </span>
                </div>

                <!-- Answer -->
                <div
                    v-if="answerMap.has(question.id)"
                    class="au-answer mt-3 ml-[26px] rounded-md p-2.5"
                >
                    <p class="text-soft-silk/90 text-[13px]">
                        {{ formatAnswer(answerMap.get(question.id)!.answer) }}
                    </p>
                </div>
            </div>
        </div>

        <!-- Submission timestamp -->
        <p v-if="formattedSubmittedAt" class="text-stone-gray/40 text-[11px]">
            Submitted {{ formattedSubmittedAt }}
        </p>
    </div>
</template>

<style scoped>
.au-pending {
    background: rgba(245, 158, 11, 0.05);
    border: 1px solid rgba(245, 158, 11, 0.12);
}

.au-pending-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: rgb(252, 211, 77);
    animation: au-pulse 2s ease-in-out infinite;
}

@keyframes au-pulse {
    0%,
    100% {
        opacity: 1;
    }
    50% {
        opacity: 0.3;
    }
}

.au-question {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.04);
}

.au-option {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.06);
    color: var(--color-soft-silk);
    opacity: 0.6;
}

.au-answer {
    background: rgba(74, 222, 128, 0.04);
}
</style>
