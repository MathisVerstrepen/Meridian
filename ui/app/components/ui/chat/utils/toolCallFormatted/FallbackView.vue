<script setup lang="ts">
import type { ToolCallDetail } from '@/types/toolCall';

const props = defineProps<{
    detail: ToolCallDetail;
}>();

const { $markedWorker } = useNuxtApp();

const argumentsHtml = ref('');
const resultHtml = ref('');
let lastRenderId = 0;

const toJsonCodeFence = (value: Record<string, unknown> | unknown[] | undefined) => {
    const formatted = JSON.stringify(value ?? {}, null, 2);
    return `\`\`\`json\n${formatted}\n\`\`\``;
};

const render = async () => {
    const renderId = ++lastRenderId;
    const [nextArgs, nextResult] = await Promise.all([
        $markedWorker.parse(toJsonCodeFence(props.detail.arguments)),
        $markedWorker.parse(toJsonCodeFence(props.detail.result)),
    ]);
    if (renderId !== lastRenderId) return;
    argumentsHtml.value = nextArgs;
    resultHtml.value = nextResult;
};

watch(
    () => props.detail,
    () => void render(),
    { immediate: true },
);
</script>

<template>
    <div class="space-y-5">
        <section>
            <p class="text-stone-gray/60 mb-1.5 text-[11px] font-medium uppercase tracking-wider">
                Arguments
            </p>
            <div
                class="fb-code-block prose prose-invert max-w-none rounded-lg bg-black/20
                    [&_pre]:bg-transparent"
                v-html="argumentsHtml"
            />
        </section>

        <section>
            <p class="text-stone-gray/60 mb-1.5 text-[11px] font-medium uppercase tracking-wider">
                Result
            </p>
            <div
                class="fb-code-block prose prose-invert max-w-none rounded-lg bg-black/20
                    [&_pre]:bg-transparent"
                v-html="resultHtml"
            />
        </section>
    </div>
</template>

<style scoped>
.fb-code-block:deep(pre) {
    max-width: 100%;
    overflow-x: hidden;
    white-space: pre-wrap;
    word-break: break-word;
    overflow-wrap: anywhere;
}

.fb-code-block:deep(pre code) {
    white-space: pre-wrap;
    word-break: break-word;
    overflow-wrap: anywhere;
}
</style>
