<script setup lang="ts">
import type { ToolCallArtifact, ToolCallDetail } from '@/types/toolCall';

const props = defineProps<{
    detail: ToolCallDetail;
}>();

const { $markedWorker } = useNuxtApp();

const codeHtml = ref('');
let lastRenderId = 0;

const args = computed(() => {
    const a = props.detail.arguments as Record<string, unknown>;
    return {
        title: String(a?.title || ''),
        code: String(a?.code || ''),
    };
});

const result = computed(() => {
    const r = props.detail.result as Record<string, unknown>;
    return {
        status: String(r?.status || ''),
        exit_code: r?.exit_code as number | undefined,
        duration_ms: r?.duration_ms as number | undefined,
        stdout: String(r?.stdout ?? ''),
        stderr: String(r?.stderr ?? ''),
        output_truncated: Boolean(r?.output_truncated),
        error: r?.error ? String(r.error) : null,
    };
});

const extractedArtifacts = computed<ToolCallArtifact[]>(() => {
    const r = props.detail.result;
    if (!r || Array.isArray(r) || typeof r !== 'object') return [];
    const rawArtifacts = (r as Record<string, unknown>).artifacts;
    if (!Array.isArray(rawArtifacts)) return [];

    return rawArtifacts.flatMap((artifact) => {
        if (!artifact || typeof artifact !== 'object' || Array.isArray(artifact)) return [];
        const a = artifact as Record<string, unknown>;
        const id = String(a.id || '').trim();
        const name = String(a.name || '').trim();
        const relativePath = String(a.relative_path || '').trim();
        const contentType = String(a.content_type || '').trim();
        const kind = a.kind === 'image' ? 'image' : 'file';
        const size = Number(a.size || 0);
        if (!id || !name || !relativePath || !contentType || !Number.isFinite(size)) return [];
        return [{ id, name, relative_path: relativePath, content_type: contentType, size, kind }];
    });
});

const durationLabel = computed(() => {
    const ms = result.value.duration_ms;
    if (ms === undefined || ms === null) return null;
    return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(2)}s`;
});

const isSuccess = computed(() => result.value.status === 'success');
const isError = computed(() =>
    ['runtime_error', 'timeout', 'memory_limit_exceeded', 'output_limit_exceeded'].includes(
        result.value.status,
    ),
);

const renderCode = async () => {
    if (!args.value.code) {
        codeHtml.value = '';
        return;
    }
    const renderId = ++lastRenderId;
    const html = await $markedWorker.parse(`\`\`\`python\n${args.value.code}\n\`\`\``);
    if (renderId !== lastRenderId) return;
    codeHtml.value = html;
};

watch(
    () => props.detail,
    () => void renderCode(),
    { immediate: true },
);
</script>

<template>
    <div class="space-y-5">
        <!-- Title + metadata row -->
        <div class="flex flex-wrap items-start justify-between gap-3">
            <p v-if="args.title" class="text-soft-silk text-[13px] font-semibold">
                {{ args.title }}
            </p>
            <div class="flex flex-wrap items-center gap-1.5 text-[11px]">
                <span
                    v-if="result.status"
                    class="inline-flex items-center gap-1 rounded-md border px-2 py-0.5 font-medium"
                    :class="
                        isSuccess
                            ? 'border-green-500/20 bg-green-500/8 text-green-400'
                            : isError
                              ? 'border-red-500/20 bg-red-500/8 text-red-400'
                              : 'border-stone-gray/15 bg-stone-gray/8 text-stone-gray'
                    "
                >
                    <span
                        class="inline-block h-1.5 w-1.5 rounded-full"
                        :class="
                            isSuccess ? 'bg-green-400' : isError ? 'bg-red-400' : 'bg-stone-gray'
                        "
                    />
                    {{ result.status.replace(/_/g, ' ') }}
                </span>
                <span
                    v-if="result.exit_code !== undefined"
                    class="bg-stone-gray/8 text-stone-gray rounded-md px-2 py-0.5"
                >
                    exit {{ result.exit_code }}
                </span>
                <span
                    v-if="durationLabel"
                    class="bg-stone-gray/8 text-stone-gray rounded-md px-2 py-0.5"
                >
                    {{ durationLabel }}
                </span>
                <span
                    v-if="result.output_truncated"
                    class="rounded-md border border-amber-500/20 bg-amber-500/8 px-2 py-0.5
                        text-amber-300"
                >
                    truncated
                </span>
            </div>
        </div>

        <!-- Code block with terminal-style chrome -->
        <section v-if="codeHtml" class="ec-code-wrapper overflow-hidden rounded-lg">
            <div class="ec-code-titlebar flex items-center gap-2 px-3.5 py-2">
                <div class="flex gap-1.5">
                    <span class="h-[7px] w-[7px] rounded-full bg-white/10" />
                    <span class="h-[7px] w-[7px] rounded-full bg-white/10" />
                    <span class="h-[7px] w-[7px] rounded-full bg-white/10" />
                </div>
                <span class="text-stone-gray/50 flex-1 text-center text-[10px] font-medium">
                    python
                </span>
            </div>
            <div
                class="ec-code-content prose prose-invert max-w-none [&_pre]:bg-transparent
                    [&_pre]:pt-0"
                v-html="codeHtml"
            />
        </section>

        <!-- stdout -->
        <section v-if="result.stdout.trim()">
            <div class="mb-1.5 flex items-center gap-2">
                <span class="h-1.5 w-1.5 rounded-full bg-green-400/70" />
                <p class="text-[12px] font-semibold">stdout</p>
            </div>
            <pre
                class="text-soft-silk/75 custom_scroll max-h-[320px] overflow-y-auto rounded-lg
                    bg-black/20 p-3.5 font-mono text-[12px] leading-relaxed wrap-break-word
                    whitespace-pre-wrap"
                >{{ result.stdout }}</pre
            >
        </section>

        <!-- stderr -->
        <section v-if="result.stderr.trim()">
            <div class="mb-1.5 flex items-center gap-2">
                <span class="h-1.5 w-1.5 rounded-full bg-red-400/70" />
                <p class="text-[12px] font-semibold">stderr</p>
            </div>
            <pre
                class="custom_scroll max-h-[320px] overflow-y-auto rounded-lg bg-red-500/4
                    p-3.5 font-mono text-[12px] leading-relaxed wrap-break-word whitespace-pre-wrap
                    text-red-300/80"
                >{{ result.stderr }}</pre
            >
        </section>

        <!-- Error -->
        <section v-if="result.error">
            <div
                class="flex items-start gap-3 rounded-lg border border-red-500/15 bg-red-500/6
                    p-3.5"
            >
                <UiIcon
                    name="MaterialSymbolsErrorCircleRounded"
                    class="mt-0.5 h-4 w-4 shrink-0 text-red-400"
                />
                <p class="text-[13px] leading-relaxed text-red-300">{{ result.error }}</p>
            </div>
        </section>

        <!-- Artifacts -->
        <section v-if="extractedArtifacts.length">
            <UiChatUtilsSandboxArtifactsTray :artifacts="extractedArtifacts" />
        </section>
    </div>
</template>

<style scoped>
.ec-code-wrapper {
    background: rgba(0, 0, 0, 0.25);
}

.ec-code-titlebar {
    background: rgba(255, 255, 255, 0.02);
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.ec-code-content:deep(pre) {
    max-width: 100%;
    overflow-x: hidden;
    white-space: pre-wrap;
    word-break: break-word;
    overflow-wrap: anywhere;
    padding: 12px 14px;
    margin: 0;
    background: #121212;
}

.ec-code-content:deep(pre code) {
    white-space: pre-wrap;
    word-break: break-word;
    overflow-wrap: anywhere;
    font-size: 12px;
    line-height: 1.65;
}
</style>
