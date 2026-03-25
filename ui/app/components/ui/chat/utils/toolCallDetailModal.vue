<script setup lang="ts">
import type { ToolCallArtifact, ToolCallDetail } from '@/types/toolCall';

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
        default:
            return {
                icon: 'MaterialSymbolsInfoRounded',
                class: 'border-stone-gray/15 bg-stone-gray/10 text-stone-gray',
                label: props.detail?.status || 'Unknown',
            };
    }
});

const extractedArtifacts = computed<ToolCallArtifact[]>(() => {
    const result = props.detail?.result;
    if (!result || Array.isArray(result) || typeof result !== 'object') {
        return [];
    }

    const rawArtifacts = (result as Record<string, unknown>).artifacts;
    if (!Array.isArray(rawArtifacts)) {
        return [];
    }

    return rawArtifacts.flatMap((artifact) => {
        if (!artifact || typeof artifact !== 'object' || Array.isArray(artifact)) {
            return [];
        }

        const typedArtifact = artifact as Record<string, unknown>;
        const id = String(typedArtifact.id || '').trim();
        const name = String(typedArtifact.name || '').trim();
        const relativePath = String(typedArtifact.relative_path || '').trim();
        const contentType = String(typedArtifact.content_type || '').trim();
        const kind = typedArtifact.kind === 'image' ? 'image' : 'file';
        const sizeValue = Number(typedArtifact.size || 0);

        if (!id || !name || !relativePath || !contentType || !Number.isFinite(sizeValue)) {
            return [];
        }

        return [
            {
                id,
                name,
                relative_path: relativePath,
                content_type: contentType,
                size: sizeValue,
                kind,
            },
        ];
    });
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

watch(
    () => [props.isOpen, props.detail] as const,
    () => {
        void renderDetailBlocks();
    },
    { immediate: true },
);
</script>

<template>
    <Teleport to="body">
        <div
            v-if="props.isOpen"
            class="bg-obsidian/70 fixed inset-0 z-120 flex items-center justify-center p-4
                backdrop-blur-sm"
            @click.self="emit('close')"
        >
            <div
                class="bg-anthracite border-stone-gray/15 text-soft-silk max-h-[85vh] w-full
                    max-w-4xl overflow-hidden rounded-2xl border shadow-2xl"
            >
                <div
                    class="border-stone-gray/10 flex items-center justify-between border-b px-5
                        py-4"
                >
                    <div class="min-w-0">
                        <p class="truncate text-sm font-semibold">
                            {{ 'Tool call: ' + props.detail?.tool_name || 'Tool call' }}
                        </p>
                        <p class="text-stone-gray text-xs">
                            {{ props.detail?.id || 'Loading...' }}
                        </p>
                    </div>
                    <button
                        class="hover:bg-stone-gray/10 flex items-center justify-center rounded-full
                            p-2 transition-colors duration-200"
                        @click="emit('close')"
                    >
                        <UiIcon name="MaterialSymbolsClose" class="h-5 w-5" />
                    </button>
                </div>

                <div v-if="props.isLoading" class="flex items-center justify-center px-5 py-16">
                    <span class="loader relative inline-block h-7 w-7" />
                </div>

                <div
                    v-else-if="props.detail"
                    class="custom_scroll max-h-[calc(85vh-5rem)] overflow-y-auto px-5 py-4"
                >
                    <div class="mb-4 flex flex-wrap gap-2 text-xs">
                        <span
                            class="inline-flex items-center gap-1.5 rounded-full border px-3 py-1
                                font-medium"
                            :class="statusMeta.class"
                        >
                            <UiIcon :name="statusMeta.icon" class="h-4 w-4" />
                            {{ statusMeta.label }}
                        </span>
                        <span
                            v-if="props.detail.model_id"
                            class="bg-stone-gray/10 rounded-full px-3 py-1"
                        >
                            Model {{ props.detail.model_id }}
                        </span>
                        <span class="bg-stone-gray/10 rounded-full px-3 py-1">
                            Node {{ props.detail.node_id }}
                        </span>
                    </div>

                    <div class="space-y-4">
                        <section>
                            <p class="mb-2 text-sm font-semibold">Arguments</p>
                            <div
                                class="tool-call-markdown prose prose-invert max-w-none rounded-lg
                                    bg-[#121212] [&_pre]:bg-transparent"
                                v-html="argumentsHtml"
                            />
                        </section>

                        <section>
                            <p class="mb-2 text-sm font-semibold">Result</p>
                            <p class="text-stone-gray mb-2 text-xs">
                                Structured tool output as stored by Meridian.
                            </p>
                            <div
                                class="tool-call-markdown prose prose-invert max-w-none rounded-lg
                                    bg-[#121212] [&_pre]:bg-transparent"
                                v-html="resultHtml"
                            />
                        </section>

                        <section v-if="extractedArtifacts.length">
                            <p class="mb-2 text-sm font-semibold">Artifacts</p>
                            <p class="text-stone-gray mb-2 text-xs">
                                Persisted files returned by this sandbox execution.
                            </p>
                            <UiChatUtilsSandboxArtifactsTray :artifacts="extractedArtifacts" />
                        </section>

                        <section>
                            <p class="mb-2 text-sm font-semibold">Model Context Payload</p>
                            <p class="text-stone-gray mb-2 text-xs">
                                Exact serialized payload injected back into the model context after
                                the tool call.
                            </p>
                            <div
                                class="tool-call-markdown prose prose-invert max-w-none rounded-lg
                                    bg-[#121212] [&_pre]:bg-transparent"
                                v-html="payloadHtml"
                            />
                        </section>
                    </div>
                </div>
            </div>
        </div>
    </Teleport>
</template>

<style scoped>
.tool-call-markdown:deep(pre) {
    max-width: 100%;
    overflow-x: hidden;
    white-space: pre-wrap;
    word-break: break-word;
    overflow-wrap: anywhere;
}

.tool-call-markdown:deep(pre code) {
    white-space: pre-wrap;
    word-break: break-word;
    overflow-wrap: anywhere;
}

.loader::after,
.loader::before {
    content: '';
    box-sizing: border-box;
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: #fff;
    position: absolute;
    left: 0;
    top: 0;
    animation: animloader 2s linear infinite;
}
.loader::before {
    animation-delay: -1s;
}
@keyframes animloader {
    0% {
        transform: scale(0);
        opacity: 1;
    }
    100% {
        transform: scale(1);
        opacity: 0;
    }
}
</style>
