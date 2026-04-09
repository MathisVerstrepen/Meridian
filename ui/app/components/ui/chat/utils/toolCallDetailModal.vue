<script setup lang="ts">
import { AnimatePresence, motion } from 'motion-v';
import { getToolDefinitionByToolCallName } from '@/constants/tools';
import type { ToolCallDetail } from '@/types/toolCall';
import { ToolEnum } from '@/types/enums';
import type { Component } from 'vue';
import ExecuteCodeView from './toolCallFormatted/ExecuteCodeView.vue';
import ImageGenerationView from './toolCallFormatted/ImageGenerationView.vue';
import WebSearchView from './toolCallFormatted/WebSearchView.vue';
import LinkExtractionView from './toolCallFormatted/LinkExtractionView.vue';
import VisualiseView from './toolCallFormatted/VisualiseView.vue';
import AskUserView from './toolCallFormatted/AskUserView.vue';
import FallbackView from './toolCallFormatted/FallbackView.vue';

interface ToolDetailMeta {
    component: Component;
    icon: string;
    label: string;
}

const TOOL_DETAIL_COMPONENTS: Record<ToolEnum, Component> = {
    [ToolEnum.WEB_SEARCH]: WebSearchView,
    [ToolEnum.LINK_EXTRACTION]: LinkExtractionView,
    [ToolEnum.IMAGE_GENERATION]: ImageGenerationView,
    [ToolEnum.EXECUTE_CODE]: ExecuteCodeView,
    [ToolEnum.VISUALISE]: VisualiseView,
    [ToolEnum.ASK_USER]: AskUserView,
};

const FALLBACK_META: ToolDetailMeta = {
    component: FallbackView,
    icon: 'MaterialSymbolsInfoRounded',
    label: 'Tool Call',
};

const props = defineProps<{
    isOpen: boolean;
    isLoading: boolean;
    detail: ToolCallDetail | null;
}>();

const emit = defineEmits(['close']);

const { $markedWorker } = useNuxtApp();

const argumentsHtml = ref('');
const resultHtml = ref('');
const payloadHtml = ref('');

let lastRenderId = 0;

const toolMeta = computed<ToolDetailMeta>(() => {
    const toolDefinition = getToolDefinitionByToolCallName(props.detail?.tool_name);
    if (!toolDefinition) return FALLBACK_META;

    return {
        component: TOOL_DETAIL_COMPONENTS[toolDefinition.type],
        icon: toolDefinition.icon,
        label: toolDefinition.name,
    };
});

const statusMeta = computed(() => {
    switch (props.detail?.status) {
        case 'success':
            return {
                icon: 'MaterialSymbolsCheckCircleRounded',
                class: 'border-green-500/20 bg-green-500/10 text-green-400',
                label: 'Success',
            };
        case 'error':
            return {
                icon: 'MaterialSymbolsErrorCircleRounded',
                class: 'border-red-500/20 bg-red-500/10 text-red-400',
                label: 'Error',
            };
        case 'pending_user_input':
            return {
                icon: 'LucideMessageCircleDashed',
                class: 'border-amber-500/20 bg-amber-500/10 text-amber-300',
                label: 'Pending user input',
            };
        default:
            return {
                icon: 'MaterialSymbolsInfoRounded',
                class: 'border-stone-gray/15 bg-stone-gray/10 text-stone-gray',
                label: props.detail?.status || 'Unknown',
            };
    }
});

const formattedCreatedAt = computed(() => {
    if (!props.detail?.created_at) return null;
    try {
        return new Date(props.detail.created_at).toLocaleString();
    } catch {
        return null;
    }
});

const toJsonCodeFence = (value: Record<string, unknown> | unknown[] | undefined) => {
    const formatted = JSON.stringify(value ?? {}, null, 2);
    return `\`\`\`json\n${formatted}\n\`\`\``;
};

const toTextCodeFence = (value: string | undefined) => {
    const formatted = value?.trim() ? value : '[empty]';
    return `\`\`\`text\n${formatted}\n\`\`\``;
};

const resetRenderedBlocks = () => {
    argumentsHtml.value = '';
    resultHtml.value = '';
    payloadHtml.value = '';
};

const renderDetailBlocks = async () => {
    if (!props.isOpen || !props.detail) {
        resetRenderedBlocks();
        return;
    }

    const renderId = ++lastRenderId;
    const [nextArgumentsHtml, nextResultHtml, nextPayloadHtml] = await Promise.all([
        $markedWorker.parse(toJsonCodeFence(props.detail.arguments)),
        $markedWorker.parse(toJsonCodeFence(props.detail.result)),
        $markedWorker.parse(toTextCodeFence(props.detail.model_context_payload)),
    ]);

    if (renderId !== lastRenderId) {
        return;
    }

    argumentsHtml.value = nextArgumentsHtml;
    resultHtml.value = nextResultHtml;
    payloadHtml.value = nextPayloadHtml;
};

const handleKeydown = (event: KeyboardEvent) => {
    if (event.key === 'Escape') emit('close');
};

watch(
    () => [props.isOpen, props.detail] as const,
    () => {
        void renderDetailBlocks();
    },
    { immediate: true },
);

watch(
    () => props.isOpen,
    (open) => {
        if (open) {
            document.addEventListener('keydown', handleKeydown);
        } else {
            document.removeEventListener('keydown', handleKeydown);
        }
    },
);

onBeforeUnmount(() => {
    document.removeEventListener('keydown', handleKeydown);
});
</script>

<template>
    <Teleport to="body">
        <AnimatePresence>
            <motion.div
                v-if="props.isOpen"
                key="tool-call-backdrop"
                class="fixed inset-0 z-120 flex items-center justify-center p-4"
                :initial="{ opacity: 0 }"
                :animate="{ opacity: 1, transition: { duration: 0.2 } }"
                :exit="{ opacity: 0, transition: { duration: 0.15 } }"
            >
                <div class="tc-backdrop absolute inset-0" @click="emit('close')" />

                <motion.div
                    key="tool-call-panel"
                    class="tc-panel bg-anthracite border-stone-gray/12 text-soft-silk relative
                        max-h-[85vh] w-full max-w-4xl overflow-hidden rounded-2xl border
                        shadow-2xl"
                    :initial="{ opacity: 0, scale: 0.92, y: 12 }"
                    :animate="{
                        opacity: 1,
                        scale: 1,
                        y: 0,
                        transition: { duration: 0.25, ease: [0.16, 1, 0.3, 1] },
                    }"
                    :exit="{
                        opacity: 0,
                        scale: 0.95,
                        y: 8,
                        transition: { duration: 0.15, ease: 'easeIn' },
                    }"
                >
                    <!-- Header -->
                    <div
                        class="tc-header border-stone-gray/8 flex items-center gap-4 border-b px-5
                            py-4"
                    >
                        <div
                            class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg
                                bg-white/4"
                        >
                            <UiIcon
                                :name="toolMeta.icon"
                                class="text-stone-gray h-[18px] w-[18px]"
                            />
                        </div>
                        <div class="min-w-0 flex-1">
                            <p class="truncate text-[13px] font-semibold leading-tight">
                                {{ toolMeta.label }}
                            </p>
                            <div class="mt-0.5 flex items-center gap-2">
                                <span class="text-stone-gray truncate font-mono text-[11px]">
                                    {{ props.detail?.id || 'Loading...' }}
                                </span>
                                <span
                                    v-if="formattedCreatedAt"
                                    class="text-stone-gray/60 hidden text-[11px] sm:inline"
                                >
                                    {{ formattedCreatedAt }}
                                </span>
                            </div>
                        </div>
                        <button
                            class="hover:bg-stone-gray/10 -mr-1 flex h-8 w-8 shrink-0 cursor-pointer
                                items-center justify-center rounded-lg transition-colors
                                duration-150"
                            @click="emit('close')"
                        >
                            <UiIcon
                                name="MaterialSymbolsClose"
                                class="text-stone-gray h-[18px] w-[18px]"
                            />
                        </button>
                    </div>

                    <!-- Loading -->
                    <div
                        v-if="props.isLoading"
                        class="flex items-center justify-center px-5 py-20"
                    >
                        <div class="tc-loader" />
                    </div>

                    <!-- Content -->
                    <div
                        v-else-if="props.detail"
                        class="custom_scroll tc-scroll max-h-[calc(85vh-4.5rem)] overflow-y-auto
                            px-5 pt-4 pb-5"
                    >
                        <!-- Status badges -->
                        <div class="mb-4 flex flex-wrap items-center gap-2 text-xs">
                            <span
                                class="inline-flex items-center gap-1.5 rounded-full border px-2.5
                                    py-[3px] font-medium"
                                :class="statusMeta.class"
                            >
                                <UiIcon :name="statusMeta.icon" class="h-3.5 w-3.5" />
                                {{ statusMeta.label }}
                            </span>
                            <span
                                v-if="props.detail.model_id"
                                class="bg-stone-gray/8 text-stone-gray rounded-full px-2.5
                                    py-[3px]"
                            >
                                {{ props.detail.model_id }}
                            </span>
                            <span
                                class="bg-stone-gray/8 text-stone-gray rounded-full px-2.5
                                    py-[3px]"
                            >
                                Node {{ props.detail.node_id }}
                            </span>
                        </div>

                        <!-- Tabs -->
                        <HeadlessTabGroup>
                            <HeadlessTabList class="tc-tabs mb-5 flex rounded-lg bg-white/3 p-0.5">
                                <HeadlessTab v-slot="{ selected }" as="template">
                                    <button
                                        class="tc-tab flex-1 cursor-pointer rounded-md px-3 py-1.5
                                            text-xs font-medium transition-all duration-150"
                                        :class="[
                                            selected
                                                ? 'tc-tab--active bg-white/8 text-soft-silk shadow-sm'
                                                : 'text-stone-gray hover:text-soft-silk/70',
                                        ]"
                                    >
                                        <UiIcon
                                            name="MaterialSymbolsLightViewAgenda"
                                            class="mr-1.5 inline-block h-3.5 w-3.5 align-[-3px]"
                                        />
                                        Formatted
                                    </button>
                                </HeadlessTab>
                                <HeadlessTab v-slot="{ selected }" as="template">
                                    <button
                                        class="tc-tab flex-1 cursor-pointer rounded-md px-3 py-1.5
                                            text-xs font-medium transition-all duration-150"
                                        :class="[
                                            selected
                                                ? 'tc-tab--active bg-white/8 text-soft-silk shadow-sm'
                                                : 'text-stone-gray hover:text-soft-silk/70',
                                        ]"
                                    >
                                        <UiIcon
                                            name="MaterialSymbolsDataObjectRounded"
                                            class="mr-1.5 inline-block h-3.5 w-3.5 align-[-3px]"
                                        />
                                        Raw
                                    </button>
                                </HeadlessTab>
                            </HeadlessTabList>

                            <HeadlessTabPanels>
                                <HeadlessTabPanel>
                                    <component
                                        :is="toolMeta.component"
                                        :detail="props.detail"
                                    />
                                </HeadlessTabPanel>

                                <HeadlessTabPanel>
                                    <div class="space-y-5">
                                        <section class="tc-section">
                                            <p class="tc-section__label">Arguments</p>
                                            <div
                                                class="tc-code-block prose prose-invert max-w-none
                                                    rounded-lg bg-[#121212]
                                                    [&_pre]:bg-transparent"
                                                v-html="argumentsHtml"
                                            />
                                        </section>

                                        <section class="tc-section">
                                            <p class="tc-section__label">Result</p>
                                            <p class="text-stone-gray/70 -mt-1 mb-2 text-[11px]">
                                                Structured tool output as stored by Meridian.
                                            </p>
                                            <div
                                                class="tc-code-block prose prose-invert max-w-none
                                                    rounded-lg bg-[#121212]
                                                    [&_pre]:bg-transparent"
                                                v-html="resultHtml"
                                            />
                                        </section>

                                        <section class="tc-section">
                                            <p class="tc-section__label">
                                                Model Context Payload
                                            </p>
                                            <p class="text-stone-gray/70 -mt-1 mb-2 text-[11px]">
                                                Exact serialized payload injected into the model
                                                context.
                                            </p>
                                            <div
                                                class="tc-code-block prose prose-invert max-w-none
                                                    rounded-lg bg-[#121212]
                                                    [&_pre]:bg-transparent"
                                                v-html="payloadHtml"
                                            />
                                        </section>
                                    </div>
                                </HeadlessTabPanel>
                            </HeadlessTabPanels>
                        </HeadlessTabGroup>
                    </div>
                </motion.div>
            </motion.div>
        </AnimatePresence>
    </Teleport>
</template>

<style scoped>
.tc-backdrop {
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(8px);
}

.tc-panel {
    box-shadow:
        0 0 0 1px rgba(255, 255, 255, 0.04),
        0 24px 48px -12px rgba(0, 0, 0, 0.5),
        0 8px 16px -4px rgba(0, 0, 0, 0.3);
}

.tc-header {
    background: linear-gradient(
        to bottom,
        rgba(255, 255, 255, 0.02),
        transparent
    );
}

.tc-loader {
    width: 28px;
    height: 28px;
    border: 2px solid rgba(255, 255, 255, 0.08);
    border-top-color: rgba(255, 255, 255, 0.5);
    border-radius: 50%;
    animation: tc-spin 0.7s linear infinite;
}

@keyframes tc-spin {
    to {
        transform: rotate(360deg);
    }
}

.tc-section__label {
    margin-bottom: 8px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.01em;
    color: var(--color-soft-silk);
}

.tc-code-block:deep(pre) {
    max-width: 100%;
    overflow-x: hidden;
    white-space: pre-wrap;
    word-break: break-word;
    overflow-wrap: anywhere;
}

.tc-code-block:deep(pre code) {
    white-space: pre-wrap;
    word-break: break-word;
    overflow-wrap: anywhere;
}

.tc-scroll {
    scrollbar-gutter: stable;
}
</style>
