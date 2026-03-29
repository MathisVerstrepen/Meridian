<script setup lang="ts">
import type {
    ToolCallDetail,
    ToolQuestionArguments,
    ToolQuestionInputType,
    ToolQuestionOption,
    ToolQuestionStep,
    ToolQuestionValidation,
} from '@/types/toolCall';

type ToolQuestionAnswerValue = string | string[] | boolean;
type ToolQuestionOtherAnswer = {
    value?: string | boolean;
    values?: string[];
    other_text: string;
    note?: string;
};
type ToolQuestionNoteAnswer = {
    value?: string | boolean;
    values?: string[];
    note?: string;
};

type AnsweredItem = {
    id: string;
    question: string;
    input_type: ToolQuestionInputType;
    answer: Record<string, unknown>;
};

const props = defineProps<{
    toolCallId: string;
}>();

const OTHER_OPTION_VALUE = '__other__';
const OTHER_OPTION_LABEL = 'Other';

const { sendMessage } = useWebSocket();
const streamStore = useStreamStore();
const { toolQuestionErrors } = storeToRefs(streamStore);
const { fetchToolCallDetail } = useToolCallDetails();

const detail = ref<ToolCallDetail | null>(null);
const isLoading = ref(true);
const isSubmitting = ref(false);
const currentStepIndex = ref(0);
const singleValues = ref<Record<string, string>>({});
const multiValues = ref<Record<string, string[]>>({});
const booleanValues = ref<Record<string, boolean | null>>({});
const textValues = ref<Record<string, string>>({});
const otherTextValues = ref<Record<string, string>>({});
const noteValues = ref<Record<string, string>>({});
const noteEditorOpen = ref<Record<string, boolean>>({});
const localError = ref('');
const isExpanded = ref(false);
let refreshTimer: number | null = null;

const normalizeInputType = (value: unknown): ToolQuestionInputType | null => {
    if (
        value === 'single_select' ||
        value === 'multi_select' ||
        value === 'boolean' ||
        value === 'text'
    ) {
        return value;
    }

    return null;
};

const normalizeOptions = (value: unknown): ToolQuestionOption[] | undefined => {
    if (!Array.isArray(value)) {
        return undefined;
    }

    const options = value
        .map((option) => {
            if (!option || typeof option !== 'object') {
                return null;
            }

            const optionRecord = option as Record<string, unknown>;

            const label = typeof optionRecord.label === 'string' ? optionRecord.label.trim() : '';
            const optionValue = typeof optionRecord.value === 'string' ? optionRecord.value : '';
            if (!label || !optionValue) {
                return null;
            }

            const normalizedOption: ToolQuestionOption = {
                label,
                value: optionValue,
                subtext:
                    typeof optionRecord.subtext === 'string' ? optionRecord.subtext.trim() : null,
            };

            return normalizedOption;
        })
        .filter((option): option is ToolQuestionOption => option !== null);

    return options.length ? options : undefined;
};

const normalizeValidation = (value: unknown): ToolQuestionValidation | undefined => {
    if (!value || typeof value !== 'object') {
        return undefined;
    }

    const validationRecord = value as Record<string, unknown>;

    return {
        placeholder:
            typeof validationRecord.placeholder === 'string' ? validationRecord.placeholder : null,
    };
};

const normalizeQuestion = (value: unknown, index: number): ToolQuestionStep | null => {
    if (!value || typeof value !== 'object') {
        return null;
    }

    const questionRecord = value as Record<string, unknown>;
    const inputType = normalizeInputType(questionRecord.input_type);
    const question =
        typeof questionRecord.question === 'string' ? questionRecord.question.trim() : '';
    if (!inputType || !question) {
        return null;
    }

    const normalizedQuestion: ToolQuestionStep = {
        id:
            typeof questionRecord.id === 'string' && questionRecord.id.trim()
                ? questionRecord.id.trim()
                : `question_${index + 1}`,
        question,
        input_type: inputType,
        help_text: typeof questionRecord.help_text === 'string' ? questionRecord.help_text : null,
        options: normalizeOptions(questionRecord.options),
        allow_other: questionRecord.allow_other === true,
        validation: normalizeValidation(questionRecord.validation),
    };

    return normalizedQuestion;
};

const normalizeToolQuestionArguments = (value: unknown): ToolQuestionArguments | null => {
    if (!value || Array.isArray(value) || typeof value !== 'object') {
        return null;
    }

    const argumentRecord = value as Record<string, unknown>;
    const title = typeof argumentRecord.title === 'string' ? argumentRecord.title : null;
    const questions = Array.isArray(argumentRecord.questions)
        ? argumentRecord.questions
              .map((question, index) => normalizeQuestion(question, index))
              .filter((question): question is ToolQuestionStep => question !== null)
        : [];

    if (questions.length > 0) {
        return {
            title,
            questions,
        };
    }

    const legacyQuestion = normalizeQuestion(argumentRecord, 0);
    if (!legacyQuestion) {
        return null;
    }

    return {
        title,
        questions: [legacyQuestion],
    };
};

const formatAnswerSummary = (answer: Record<string, unknown>): string => {
    if (typeof answer.other_text === 'string' && answer.other_text.trim()) {
        if (Array.isArray(answer.labels)) {
            return answer.labels
                .filter((label): label is string => typeof label === 'string')
                .map((label) =>
                    label === OTHER_OPTION_LABEL
                        ? `${OTHER_OPTION_LABEL}: ${answer.other_text}`
                        : label,
                )
                .join(', ');
        }

        if (typeof answer.label === 'string' && answer.label === OTHER_OPTION_LABEL) {
            return `${OTHER_OPTION_LABEL}: ${answer.other_text}`;
        }
    }

    if (Array.isArray(answer.labels)) {
        return answer.labels
            .filter((label): label is string => typeof label === 'string')
            .join(', ');
    }

    if (typeof answer.label === 'string') {
        return answer.label;
    }

    if (Array.isArray(answer.values)) {
        return answer.values
            .filter((value): value is string => typeof value === 'string')
            .join(', ');
    }

    if (typeof answer.value === 'boolean') {
        return answer.value ? 'Yes' : 'No';
    }

    if (typeof answer.value === 'string') {
        return answer.value;
    }

    return '';
};

const getAnswerNote = (answer: Record<string, unknown>): string => {
    if (typeof answer.note !== 'string') {
        return '';
    }

    return answer.note.trim();
};

const normalizeAnsweredItems = (result: unknown): AnsweredItem[] => {
    if (!result || Array.isArray(result) || typeof result !== 'object') {
        return [];
    }

    const resultRecord = result as Record<string, unknown>;

    if (Array.isArray(resultRecord.answers)) {
        return resultRecord.answers
            .map((item, index) => {
                if (!item || typeof item !== 'object') {
                    return null;
                }

                const itemRecord = item as Record<string, unknown>;
                const inputType = normalizeInputType(itemRecord.input_type);
                if (
                    typeof itemRecord.question !== 'string' ||
                    !inputType ||
                    !itemRecord.answer ||
                    Array.isArray(itemRecord.answer) ||
                    typeof itemRecord.answer !== 'object'
                ) {
                    return null;
                }

                return {
                    id:
                        typeof itemRecord.id === 'string' && itemRecord.id.trim()
                            ? itemRecord.id.trim()
                            : `question_${index + 1}`,
                    question: itemRecord.question,
                    input_type: inputType,
                    answer: itemRecord.answer,
                };
            })
            .filter((item): item is AnsweredItem => item !== null);
    }

    const inputType = normalizeInputType(resultRecord.input_type);
    if (
        typeof resultRecord.question === 'string' &&
        inputType &&
        resultRecord.answer &&
        !Array.isArray(resultRecord.answer) &&
        typeof resultRecord.answer === 'object'
    ) {
        return [
            {
                id: 'question_1',
                question: resultRecord.question,
                input_type: inputType,
                answer: resultRecord.answer as Record<string, unknown>,
            },
        ];
    }

    return [];
};

const typedArguments = computed<ToolQuestionArguments | null>(() =>
    normalizeToolQuestionArguments(detail.value?.arguments),
);

const answeredItems = computed<AnsweredItem[]>(() => normalizeAnsweredItems(detail.value?.result));

const remoteError = computed(() => toolQuestionErrors.value.get(props.toolCallId) || '');

const isPending = computed(() => detail.value?.status === 'pending_user_input');
const totalQuestions = computed(() => typedArguments.value?.questions.length ?? 0);
const isMultiStep = computed(() => totalQuestions.value > 1);
const currentQuestion = computed<ToolQuestionStep | null>(() => {
    if (!typedArguments.value) {
        return null;
    }

    return typedArguments.value.questions[currentStepIndex.value] ?? null;
});
const getRenderedOptions = (question: ToolQuestionStep): ToolQuestionOption[] => {
    const options = question.options || [];
    if (!question.allow_other) {
        return options;
    }

    return options.filter((option) => {
        const normalizedValue = option.value.trim().toLowerCase();
        const normalizedLabel = option.label.trim().toLowerCase();
        return (
            normalizedValue !== OTHER_OPTION_VALUE &&
            normalizedValue !== 'other' &&
            normalizedLabel !== 'other'
        );
    });
};
const isLastStep = computed(() => currentStepIndex.value === totalQuestions.value - 1);
const currentQuestionTextValidationMessage = computed(() => '');

const cardTitle = computed(() => {
    if (!typedArguments.value) {
        return '';
    }

    if (typedArguments.value.title) {
        return typedArguments.value.title;
    }

    if (isMultiStep.value) {
        return `Answer ${totalQuestions.value} questions`;
    }

    return currentQuestion.value?.question || '';
});

const resultErrorMessage = computed(() => {
    const result = detail.value?.result;
    if (!result || Array.isArray(result) || typeof result !== 'object') {
        return 'This question can no longer accept an answer.';
    }

    const error = (result as Record<string, unknown>).error;
    return typeof error === 'string' && error
        ? error
        : 'This question can no longer accept an answer.';
});

const getQuestionValidationMessage = (
    question: ToolQuestionStep,
    includeRequired: boolean = false,
): string => {
    switch (question.input_type) {
        case 'boolean':
            return includeRequired && booleanValues.value[question.id] === null
                ? 'Choose Yes or No.'
                : '';
        case 'single_select':
            if (!singleValues.value[question.id]) {
                return includeRequired ? 'Select one option.' : '';
            }
            if (
                question.allow_other &&
                singleValues.value[question.id] === OTHER_OPTION_VALUE &&
                !otherTextValues.value[question.id]?.trim()
            ) {
                return 'Enter a custom value for Other.';
            }
            return '';
        case 'multi_select': {
            const selectedValues = multiValues.value[question.id] || [];
            if (!selectedValues.length) {
                return includeRequired ? 'Select at least one option.' : '';
            }
            if (
                question.allow_other &&
                selectedValues.includes(OTHER_OPTION_VALUE) &&
                !otherTextValues.value[question.id]?.trim()
            ) {
                return 'Enter a custom value for Other.';
            }
            return '';
        }
        case 'text': {
            const value = textValues.value[question.id] || '';
            if (!value) {
                return includeRequired ? 'Enter a value.' : '';
            }
            return value.trim() ? '' : 'Enter a value.';
        }
        default:
            return '';
    }
};

const isQuestionValid = (question: ToolQuestionStep): boolean =>
    !getQuestionValidationMessage(question, true);

const getQuestionAnswerPayload = (
    question: ToolQuestionStep,
): ToolQuestionAnswerValue | ToolQuestionOtherAnswer | ToolQuestionNoteAnswer | null => {
    const note = (noteValues.value[question.id] || '').trim();
    const attachNote = (
        payload: ToolQuestionAnswerValue | ToolQuestionOtherAnswer | ToolQuestionNoteAnswer,
    ): ToolQuestionAnswerValue | ToolQuestionOtherAnswer | ToolQuestionNoteAnswer => {
        if (!note) {
            return payload;
        }

        if (Array.isArray(payload)) {
            return {
                values: [...payload],
                note,
            };
        }

        if (typeof payload === 'string' || typeof payload === 'boolean') {
            return {
                value: payload,
                note,
            };
        }

        return {
            ...payload,
            note,
        };
    };

    switch (question.input_type) {
        case 'boolean':
            return booleanValues.value[question.id] === null
                ? null
                : attachNote(booleanValues.value[question.id]);
        case 'single_select':
            if (question.allow_other && singleValues.value[question.id] === OTHER_OPTION_VALUE) {
                return attachNote({
                    value: OTHER_OPTION_VALUE,
                    other_text: (otherTextValues.value[question.id] || '').trim(),
                });
            }
            return singleValues.value[question.id]
                ? attachNote(singleValues.value[question.id])
                : null;
        case 'multi_select':
            if (
                question.allow_other &&
                (multiValues.value[question.id] || []).includes(OTHER_OPTION_VALUE)
            ) {
                return attachNote({
                    values: [...(multiValues.value[question.id] || [])],
                    other_text: (otherTextValues.value[question.id] || '').trim(),
                });
            }
            return attachNote([...(multiValues.value[question.id] || [])]);
        case 'text':
            return textValues.value[question.id]
                ? attachNote(textValues.value[question.id])
                : null;
        default:
            return null;
    }
};

const canMoveForward = computed(() => {
    if (!currentQuestion.value || !isPending.value || isSubmitting.value) {
        return false;
    }

    return isQuestionValid(currentQuestion.value);
});

const canSubmit = computed(() => {
    if (!typedArguments.value || !isPending.value || isSubmitting.value) {
        return false;
    }

    return typedArguments.value.questions.every((question) => isQuestionValid(question));
});

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

const buildAnswerPayload = (): Record<
    string,
    ToolQuestionAnswerValue | ToolQuestionOtherAnswer | ToolQuestionNoteAnswer
> | null => {
    if (!typedArguments.value) {
        return null;
    }

    const answerPayload: Record<
        string,
        ToolQuestionAnswerValue | ToolQuestionOtherAnswer | ToolQuestionNoteAnswer
    > = {};
    for (const question of typedArguments.value.questions) {
        const value = getQuestionAnswerPayload(question);
        if (value === null) {
            return null;
        }
        answerPayload[question.id] = value;
    }

    return answerPayload;
};

const submitAnswer = async () => {
    localError.value = '';
    streamStore.clearToolQuestionError(props.toolCallId);

    if (!typedArguments.value || !detail.value?.node_id) {
        localError.value = 'The answer is incomplete.';
        return;
    }

    const invalidQuestionIndex = typedArguments.value.questions.findIndex(
        (question) => !isQuestionValid(question),
    );
    if (invalidQuestionIndex !== -1) {
        currentStepIndex.value = invalidQuestionIndex;
        localError.value = getQuestionValidationMessage(
            typedArguments.value.questions[invalidQuestionIndex],
            true,
        );
        return;
    }

    const answer = buildAnswerPayload();
    if (!answer) {
        localError.value = 'The answer is incomplete.';
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

const goToPreviousStep = () => {
    localError.value = '';
    currentStepIndex.value = Math.max(0, currentStepIndex.value - 1);
};

const goToNextStep = () => {
    if (!currentQuestion.value) {
        return;
    }

    const validationMessage = getQuestionValidationMessage(currentQuestion.value, true);
    if (validationMessage) {
        localError.value = validationMessage;
        return;
    }

    localError.value = '';
    currentStepIndex.value = Math.min(totalQuestions.value - 1, currentStepIndex.value + 1);
};

const handleTextQuestionEnter = async (event: KeyboardEvent) => {
    if (event.isComposing || !currentQuestion.value || currentQuestion.value.input_type !== 'text') {
        return;
    }

    event.preventDefault();

    if (isLastStep.value) {
        await submitAnswer();
        return;
    }

    goToNextStep();
};

const toggleMultiValue = (questionId: string, value: string, checked: boolean) => {
    const currentValues = multiValues.value[questionId] || [];
    if (checked) {
        if (!currentValues.includes(value)) {
            multiValues.value = {
                ...multiValues.value,
                [questionId]: [...currentValues, value],
            };
        }
        return;
    }

    multiValues.value = {
        ...multiValues.value,
        [questionId]: currentValues.filter((item) => item !== value),
    };
};

watch(
    typedArguments,
    (value) => {
        const questions = value?.questions ?? [];
        currentStepIndex.value = Math.min(
            currentStepIndex.value,
            Math.max(questions.length - 1, 0),
        );

        const nextSingleValues: Record<string, string> = {};
        const nextMultiValues: Record<string, string[]> = {};
        const nextBooleanValues: Record<string, boolean | null> = {};
        const nextTextValues: Record<string, string> = {};
        const nextOtherTextValues: Record<string, string> = {};
        const nextNoteValues: Record<string, string> = {};
        const nextNoteEditorOpen: Record<string, boolean> = {};

        for (const question of questions) {
            nextSingleValues[question.id] = singleValues.value[question.id] || '';
            nextMultiValues[question.id] = [...(multiValues.value[question.id] || [])];
            nextBooleanValues[question.id] =
                question.id in booleanValues.value ? booleanValues.value[question.id] : null;
            nextTextValues[question.id] = textValues.value[question.id] || '';
            nextOtherTextValues[question.id] = otherTextValues.value[question.id] || '';
            nextNoteValues[question.id] = noteValues.value[question.id] || '';
            nextNoteEditorOpen[question.id] =
                noteEditorOpen.value[question.id] || !!noteValues.value[question.id]?.trim();
        }

        singleValues.value = nextSingleValues;
        multiValues.value = nextMultiValues;
        booleanValues.value = nextBooleanValues;
        textValues.value = nextTextValues;
        otherTextValues.value = nextOtherTextValues;
        noteValues.value = nextNoteValues;
        noteEditorOpen.value = nextNoteEditorOpen;
    },
    { immediate: true },
);

watch(currentStepIndex, () => {
    localError.value = '';
});

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
    <div
        data-testid="tool-question-card"
        class="tq-card group border-stone-gray/10 bg-anthracite/30 my-3 overflow-hidden rounded-xl
            border backdrop-blur-sm"
    >
        <!-- Loading skeleton -->
        <div v-if="isLoading" class="flex items-center gap-3 px-4 py-4">
            <div class="bg-stone-gray/15 h-4 w-4 animate-pulse rounded-full" />
            <div class="flex-1 space-y-2">
                <div class="bg-stone-gray/10 h-3 w-2/3 animate-pulse rounded" />
                <div class="bg-stone-gray/8 h-2.5 w-1/3 animate-pulse rounded" />
            </div>
        </div>

        <template v-else-if="detail && typedArguments && currentQuestion">
            <!-- Header -->
            <div
                class="flex items-center gap-3 px-4 pt-3 pb-3"
                :class="detail.status === 'success' ? 'cursor-pointer select-none' : ''"
                @click="detail.status === 'success' && (isExpanded = !isExpanded)"
            >
                <div
                    class="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg"
                    :class="
                        detail.status === 'success'
                            ? 'bg-olive-grove/15 text-olive-grove'
                            : detail.status === 'pending_user_input'
                              ? 'bg-ember-glow/12 text-ember-glow'
                              : 'bg-red-500/10 text-red-400'
                    "
                >
                    <UiIcon
                        v-if="detail.status === 'success'"
                        name="MaterialSymbolsCheckCircleRounded"
                        class="h-4 w-4"
                    />
                    <UiIcon
                        v-else-if="detail.status === 'pending_user_input'"
                        name="LucideMessageCircleDashed"
                        class="h-3.5 w-3.5"
                    />
                    <UiIcon v-else name="MaterialSymbolsErrorCircleRounded" class="h-4 w-4" />
                </div>

                <p
                    class="text-soft-silk not-prose w-full text-[13px] leading-snug font-semibold
                        tracking-tight"
                >
                    {{ cardTitle }}
                </p>

                <span
                    v-if="detail.status !== 'success'"
                    class="shrink-0 rounded-md px-2 py-0.5 text-[10px] font-bold tracking-wider
                        uppercase"
                    :class="
                        detail.status === 'pending_user_input'
                            ? 'bg-ember-glow/10 text-ember-glow/80'
                            : 'bg-red-500/10 text-red-400/80'
                    "
                >
                    {{ detail.status === 'pending_user_input' ? 'Awaiting' : detail.status }}
                </span>
                <span
                    v-else
                    class="bg-olive-grove/10 text-olive-grove/80 flex shrink-0 items-center gap-0.5
                        rounded-md py-0.5 pr-1 pl-2 text-[10px] font-bold tracking-wider uppercase"
                >
                    Answered
                    <UiIcon
                        name="FlowbiteChevronDownOutline"
                        class="text-olive-grove/80 h-4 w-4 transition-transform duration-200"
                        :class="isExpanded ? 'rotate-180' : ''"
                    />
                </span>
            </div>

            <!-- Question text (shown in multi-step or when title is separate) -->
            <div v-if="(isMultiStep || typedArguments.title) && isPending" class="px-4">
                <p class="text-soft-silk/90 not-prose text-xs leading-relaxed font-medium">
                    {{ currentQuestion.question }}
                </p>
            </div>
            <div v-if="currentQuestion.help_text && isPending" class="px-4">
                <p class="text-stone-gray/70 not-prose text-[11px] leading-relaxed">
                    {{ currentQuestion.help_text }}
                </p>
            </div>

            <!-- Success: answered items (collapsed by default) -->
            <div
                v-if="detail.status === 'success'"
                class="tq-collapse-wrapper"
                :class="isExpanded ? 'tq-collapse-open' : ''"
            >
                <div class="tq-collapse-inner">
                    <div class="space-y-1 px-3 pt-2.5 pb-3.5">
                        <div
                            v-for="item in answeredItems"
                            :key="item.id"
                            class="bg-obsidian/25 flex flex-col items-baseline gap-1 rounded-lg px-3
                                py-2"
                        >
                            <span
                                class="text-stone-gray/60 shrink-0 text-[10px] font-semibold
                                    tracking-wider uppercase"
                            >
                                {{ item.question }}
                            </span>
                            <span class="text-soft-silk text-xs font-medium">
                                {{ formatAnswerSummary(item.answer) }}
                            </span>
                            <span
                                v-if="getAnswerNote(item.answer)"
                                class="text-stone-gray/70 text-[11px] leading-relaxed"
                            >
                                Note: {{ getAnswerNote(item.answer) }}
                            </span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Pending: interactive form -->
            <div
                v-else-if="detail.status === 'pending_user_input'"
                class="space-y-2.5 px-4 pt-2.5 pb-3.5"
            >
                <!-- Multi-step progress bar -->
                <div v-if="isMultiStep" class="flex items-center gap-1">
                    <div
                        v-for="(question, index) in typedArguments.questions"
                        :key="question.id"
                        class="relative h-1 flex-1 overflow-hidden rounded-full transition-all
                            duration-300"
                        :class="index <= currentStepIndex ? 'bg-stone-gray/8' : 'bg-white/3'"
                    >
                        <div
                            class="absolute inset-y-0 left-0 rounded-full transition-all
                                duration-500 ease-out"
                            :class="
                                index < currentStepIndex
                                    ? 'bg-stone-gray/50 w-full'
                                    : index === currentStepIndex
                                      ? `from-ember-glow/70 to-golden-ochre/50 w-full
                                        bg-linear-to-r`
                                      : 'w-0'
                            "
                        />
                    </div>
                </div>

                <!-- Single select -->
                <div
                    v-if="currentQuestion.input_type === 'single_select' && currentQuestion.options"
                    class="space-y-1"
                >
                    <label
                        v-for="option in getRenderedOptions(currentQuestion)"
                        :key="option.value"
                        class="tq-option group/opt flex cursor-pointer items-center gap-2.5
                            rounded-lg border px-3 py-2 text-xs transition-all duration-150"
                        :class="
                            singleValues[currentQuestion.id] === option.value
                                ? 'border-ember-glow/30 bg-ember-glow/6'
                                : `border-stone-gray/8 bg-obsidian/20 hover:border-stone-gray/18
                                    hover:bg-obsidian/35`
                        "
                    >
                        <span
                            class="flex h-4 w-4 shrink-0 items-center justify-center
                                rounded-full border transition-all duration-150"
                            :class="
                                singleValues[currentQuestion.id] === option.value
                                    ? 'border-ember-glow bg-ember-glow'
                                    : `border-stone-gray/25
                                        group-hover/opt:border-stone-gray/40`
                            "
                        >
                            <span
                                v-if="singleValues[currentQuestion.id] === option.value"
                                class="bg-obsidian h-1.5 w-1.5 rounded-full"
                            />
                        </span>
                        <input
                            v-model="singleValues[currentQuestion.id]"
                            type="radio"
                            :name="currentQuestion.id"
                            :value="option.value"
                            class="sr-only"
                        />
                        <span class="min-w-0">
                            <span
                                class="block transition-colors duration-150"
                                :class="
                                    singleValues[currentQuestion.id] === option.value
                                        ? 'text-soft-silk font-medium'
                                        : 'text-stone-gray group-hover/opt:text-soft-silk/80'
                                "
                            >
                                {{ option.label }}
                            </span>
                            <span
                                v-if="option.subtext"
                                class="text-stone-gray/60 mt-0.5 block text-[10px]
                                    leading-tight"
                            >
                                {{ option.subtext }}
                            </span>
                        </span>
                    </label>
                    <label
                        v-if="currentQuestion.allow_other"
                        class="tq-option group/opt flex cursor-pointer items-start gap-2.5
                            rounded-lg border px-3 py-2 text-xs transition-all duration-150"
                        :class="
                            singleValues[currentQuestion.id] === OTHER_OPTION_VALUE
                                ? 'border-ember-glow/30 bg-ember-glow/6'
                                : `border-stone-gray/8 bg-obsidian/20 hover:border-stone-gray/18
                                    hover:bg-obsidian/35`
                        "
                    >
                        <span
                            class="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center
                                rounded-full border transition-all duration-150"
                            :class="
                                singleValues[currentQuestion.id] === OTHER_OPTION_VALUE
                                    ? 'border-ember-glow bg-ember-glow'
                                    : 'border-stone-gray/25 group-hover/opt:border-stone-gray/40'
                            "
                        >
                            <span
                                v-if="singleValues[currentQuestion.id] === OTHER_OPTION_VALUE"
                                class="bg-obsidian h-1.5 w-1.5 rounded-full"
                            />
                        </span>
                        <input
                            v-model="singleValues[currentQuestion.id]"
                            type="radio"
                            :name="currentQuestion.id"
                            :value="OTHER_OPTION_VALUE"
                            class="sr-only"
                        />
                        <span class="min-w-0 flex-1">
                            <span class="text-stone-gray block mt-0.5">
                                {{ OTHER_OPTION_LABEL }}
                            </span>
                            <input
                                v-if="singleValues[currentQuestion.id] === OTHER_OPTION_VALUE"
                                v-model="otherTextValues[currentQuestion.id]"
                                type="text"
                                placeholder="Please specify"
                                class="border-stone-gray/12 bg-obsidian/30 text-soft-silk
                                    placeholder:text-stone-gray/30 focus:border-ember-glow/35 mt-2
                                    h-8 w-full rounded-md border px-2.5 text-[11px]
                                    transition-colors duration-150 focus:outline-none"
                                @click.stop
                            />
                        </span>
                    </label>
                </div>

                <!-- Multi select -->
                <div
                    v-else-if="
                        currentQuestion.input_type === 'multi_select' && currentQuestion.options
                    "
                    class="space-y-1"
                >
                    <label
                        v-for="option in getRenderedOptions(currentQuestion)"
                        :key="option.value"
                        class="tq-option group/opt flex cursor-pointer items-center gap-2.5
                            rounded-lg border px-3 py-2 text-xs transition-all duration-150"
                        :class="[
                            (multiValues[currentQuestion.id] || []).includes(option.value)
                                ? 'border-ember-glow/30 bg-ember-glow/6'
                                : `border-stone-gray/8 bg-obsidian/20 hover:border-stone-gray/18
                                    hover:bg-obsidian/35`,
                        ]"
                    >
                        <span
                            class="flex h-4 w-4 shrink-0 items-center justify-center rounded border
                                transition-all duration-150"
                            :class="
                                (multiValues[currentQuestion.id] || []).includes(option.value)
                                    ? 'border-ember-glow bg-ember-glow'
                                    : 'border-stone-gray/25 group-hover/opt:border-stone-gray/40'
                            "
                        >
                            <svg
                                v-if="
                                    (multiValues[currentQuestion.id] || []).includes(option.value)
                                "
                                class="text-obsidian h-2.5 w-2.5"
                                viewBox="0 0 12 12"
                                fill="none"
                            >
                                <path
                                    d="M2.5 6L5 8.5L9.5 3.5"
                                    stroke="currentColor"
                                    stroke-width="2"
                                    stroke-linecap="round"
                                    stroke-linejoin="round"
                                />
                            </svg>
                        </span>
                        <input
                            type="checkbox"
                            :checked="
                                (multiValues[currentQuestion.id] || []).includes(option.value)
                            "
                            class="sr-only"
                            @change="
                                toggleMultiValue(
                                    currentQuestion.id,
                                    option.value,
                                    ($event.target as HTMLInputElement).checked,
                                )
                            "
                        />
                        <span class="min-w-0">
                            <span
                                class="block transition-colors duration-150"
                                :class="
                                    (multiValues[currentQuestion.id] || []).includes(option.value)
                                        ? 'text-soft-silk font-medium'
                                        : 'text-stone-gray group-hover/opt:text-soft-silk/80'
                                "
                            >
                                {{ option.label }}
                            </span>
                            <span
                                v-if="option.subtext"
                                class="text-stone-gray/60 mt-0.5 block text-[10px] leading-tight"
                            >
                                {{ option.subtext }}
                            </span>
                        </span>
                    </label>
                    <label
                        v-if="currentQuestion.allow_other"
                        class="tq-option group/opt flex cursor-pointer items-start gap-2.5
                            rounded-lg border px-3 py-2 text-xs transition-all duration-150"
                        :class="
                            (multiValues[currentQuestion.id] || []).includes(OTHER_OPTION_VALUE)
                                ? 'border-ember-glow/30 bg-ember-glow/6'
                                : `border-stone-gray/8 bg-obsidian/20 hover:border-stone-gray/18
                                    hover:bg-obsidian/35`
                        "
                    >
                        <span
                            class="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded
                                border transition-all duration-150"
                            :class="
                                (multiValues[currentQuestion.id] || []).includes(OTHER_OPTION_VALUE)
                                    ? 'border-ember-glow bg-ember-glow'
                                    : 'border-stone-gray/25 group-hover/opt:border-stone-gray/40'
                            "
                        >
                            <svg
                                v-if="
                                    (multiValues[currentQuestion.id] || []).includes(
                                        OTHER_OPTION_VALUE,
                                    )
                                "
                                class="text-obsidian h-2.5 w-2.5"
                                viewBox="0 0 12 12"
                                fill="none"
                            >
                                <path
                                    d="M2.5 6L5 8.5L9.5 3.5"
                                    stroke="currentColor"
                                    stroke-width="2"
                                    stroke-linecap="round"
                                    stroke-linejoin="round"
                                />
                            </svg>
                        </span>
                        <input
                            type="checkbox"
                            :checked="
                                (multiValues[currentQuestion.id] || []).includes(OTHER_OPTION_VALUE)
                            "
                            class="sr-only"
                            @change="
                                toggleMultiValue(
                                    currentQuestion.id,
                                    OTHER_OPTION_VALUE,
                                    ($event.target as HTMLInputElement).checked,
                                )
                            "
                        />
                        <span class="min-w-0 flex-1">
                            <span class="text-stone-gray block mt-0.5">
                                {{ OTHER_OPTION_LABEL }}
                            </span>
                            <input
                                v-if="
                                    (multiValues[currentQuestion.id] || []).includes(
                                        OTHER_OPTION_VALUE,
                                    )
                                "
                                v-model="otherTextValues[currentQuestion.id]"
                                type="text"
                                placeholder="Please specify"
                                class="border-stone-gray/12 bg-obsidian/30 text-soft-silk
                                    placeholder:text-stone-gray/30 focus:border-ember-glow/35 mt-2
                                    h-8 w-full rounded-md border px-2.5 text-[11px]
                                    transition-colors duration-150 focus:outline-none"
                                @click.stop
                            />
                        </span>
                    </label>
                </div>

                <!-- Boolean -->
                <div v-else-if="currentQuestion.input_type === 'boolean'" class="flex gap-2">
                    <button
                        type="button"
                        class="flex-1 rounded-lg border px-4 py-2.5 text-xs font-semibold
                            tracking-wide transition-all duration-200"
                        :class="
                            booleanValues[currentQuestion.id] === true
                                ? `border-ember-glow/30 bg-ember-glow/10 text-ember-glow
                                    shadow-ember-glow/20 shadow-[0_0_12px_-3px]`
                                : `border-stone-gray/10 bg-obsidian/20 text-stone-gray
                                    hover:border-stone-gray/20 hover:bg-obsidian/35
                                    hover:text-soft-silk/80`
                        "
                        @click="booleanValues[currentQuestion.id] = true"
                    >
                        Yes
                    </button>
                    <button
                        type="button"
                        class="flex-1 rounded-lg border px-4 py-2.5 text-xs font-semibold
                            tracking-wide transition-all duration-200"
                        :class="
                            booleanValues[currentQuestion.id] === false
                                ? `border-ember-glow/30 bg-ember-glow/10 text-ember-glow
                                    shadow-ember-glow/20 shadow-[0_0_12px_-3px]`
                                : `border-stone-gray/10 bg-obsidian/20 text-stone-gray
                                    hover:border-stone-gray/20 hover:bg-obsidian/35
                                    hover:text-soft-silk/80`
                        "
                        @click="booleanValues[currentQuestion.id] = false"
                    >
                        No
                    </button>
                </div>

                <!-- Text input -->
                <div v-else-if="currentQuestion.input_type === 'text'" class="space-y-1.5">
                    <input
                        v-model="textValues[currentQuestion.id]"
                        type="text"
                        :placeholder="
                            currentQuestion.validation?.placeholder || 'Type your answer...'
                        "
                        class="border-stone-gray/12 bg-obsidian/30 text-soft-silk
                            placeholder:text-stone-gray/30 focus:border-ember-glow/35
                            focus:ring-ember-glow/10 h-9 w-full rounded-lg border px-3 text-xs
                            transition-colors duration-150 focus:ring-1 focus:outline-none"
                        @keydown.enter="handleTextQuestionEnter"
                    />
                    <p
                        v-if="currentQuestionTextValidationMessage"
                        class="flex items-center gap-1.5 text-[11px] text-red-400/90"
                    >
                        <span class="inline-block h-1 w-1 rounded-full bg-red-400/70" />
                        {{ currentQuestionTextValidationMessage }}
                    </p>
                </div>

                <div
                    v-if="
                        noteEditorOpen[currentQuestion.id] ||
                        Boolean(noteValues[currentQuestion.id]?.trim())
                    "
                    class="space-y-1.5"
                >
                    <textarea
                        v-model="noteValues[currentQuestion.id]"
                        rows="3"
                        placeholder="Add optional context about your answer"
                        class="border-stone-gray/12 bg-obsidian/25 text-soft-silk
                            placeholder:text-stone-gray/30 focus:border-ember-glow/35
                            focus:ring-ember-glow/10 min-h-[78px] w-full rounded-lg border px-3
                            py-2 text-xs leading-relaxed transition-colors duration-150
                            focus:ring-1 focus:outline-none"
                    />
                    <p class="text-stone-gray/60 text-[10px] leading-relaxed italic not-prose">
                        This note is extra context. It will be sent with your answer, but it does
                        not replace the selected value.
                    </p>
                </div>

                <!-- Error message -->
                <p
                    v-if="localError || remoteError"
                    class="flex items-center gap-1.5 text-[11px] text-red-400/90"
                >
                    <span class="inline-block h-1 w-1 shrink-0 rounded-full bg-red-400/70" />
                    {{ localError || remoteError }}
                </p>

                <!-- Navigation buttons -->
                <div class="flex items-center justify-between gap-2 pt-1">
                    <button
                        v-if="isMultiStep"
                        type="button"
                        class="text-stone-gray hover:text-soft-silk/80 rounded-md px-2.5 py-1.5
                            text-[11px] font-semibold tracking-wide transition-all duration-150
                            hover:bg-white/3 disabled:pointer-events-none disabled:opacity-25"
                        :disabled="currentStepIndex === 0 || isSubmitting"
                        @click="goToPreviousStep"
                    >
                        Back
                    </button>
                    <div v-else />

                    <div class="flex items-center gap-2">
                        <button
                            type="button"
                            class="text-stone-gray hover:text-soft-silk/80 rounded-lg border
                                border-transparent px-2.5 py-1 text-[11px] font-semibold
                                tracking-wide transition-all duration-150 hover:bg-white/3"
                            :class="
                                noteEditorOpen[currentQuestion.id] ||
                                Boolean(noteValues[currentQuestion.id]?.trim())
                                    ? 'border-ember-glow/18 bg-ember-glow/6 text-soft-silk'
                                    : ''
                            "
                            :disabled="isSubmitting"
                            @click="
                                noteEditorOpen[currentQuestion.id] =
                                    !noteEditorOpen[currentQuestion.id]
                            "
                        >
                            Add Note
                        </button>
                        <button
                            v-if="!isLastStep"
                            type="button"
                            class="tq-btn-primary rounded-lg px-4 py-1.5 text-xs font-semibold
                                tracking-wide transition-all duration-200
                                disabled:pointer-events-none disabled:opacity-25"
                            :disabled="!canMoveForward"
                            @click="goToNextStep"
                        >
                            Next
                        </button>
                        <button
                            v-else
                            type="button"
                            class="tq-btn-primary rounded-lg px-4 py-1.5 text-xs font-semibold
                                tracking-wide transition-all duration-200
                                disabled:pointer-events-none disabled:opacity-25"
                            :disabled="!canSubmit"
                            @click="submitAnswer"
                        >
                            <span v-if="isSubmitting" class="flex items-center gap-1.5">
                                <span
                                    class="tq-spinner border-obsidian/30 border-t-obsidian h-3
                                        w-3 rounded-full border-2"
                                />
                                Sending
                            </span>
                            <span v-else>Submit</span>
                        </button>
                    </div>
                </div>
            </div>

            <!-- Error / expired state -->
            <div v-else class="flex items-start gap-2.5 px-4 pt-2.5 pb-3.5">
                <UiIcon
                    name="MaterialSymbolsErrorCircleRounded"
                    class="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-400/70"
                />
                <p class="text-[11px] leading-relaxed text-red-400/80">
                    {{ resultErrorMessage }}
                </p>
            </div>
        </template>
    </div>
</template>

<style scoped>
.tq-card {
    box-shadow:
        0 1px 3px -1px rgba(0, 0, 0, 0.25),
        0 0 0 1px rgba(255, 252, 242, 0.02);
}

.tq-btn-primary {
    background: linear-gradient(
        135deg,
        var(--color-ember-glow),
        color-mix(in oklab, var(--color-ember-glow) 80%, var(--color-golden-ochre))
    );
    color: var(--color-obsidian);
    box-shadow: 0 1px 8px -2px color-mix(in oklab, var(--color-ember-glow) 35%, transparent);
}

.tq-btn-primary:hover:not(:disabled) {
    box-shadow: 0 2px 14px -3px color-mix(in oklab, var(--color-ember-glow) 50%, transparent);
    filter: brightness(1.08);
}

.tq-collapse-wrapper {
    display: grid;
    grid-template-rows: 0fr;
    transition: grid-template-rows 0.3s ease-out;
}

.tq-collapse-inner {
    overflow: hidden;
}

.tq-collapse-open {
    grid-template-rows: 1fr;
}

.tq-spinner {
    animation: tq-spin 0.6s linear infinite;
}

@keyframes tq-spin {
    to {
        transform: rotate(360deg);
    }
}
</style>
