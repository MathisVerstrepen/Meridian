<script setup lang="ts">
import type { ToolCallArtifact, ToolCallDetail } from '@/types/toolCall';

const props = defineProps<{
    detail: ToolCallDetail;
}>();

const args = computed(() => {
    const a = props.detail.arguments as Record<string, unknown>;
    return {
        instructions: String(a?.instructions || ''),
        output_mode: a?.output_mode ? String(a.output_mode) : null,
        title: a?.title ? String(a.title) : null,
        difficulty: a?.difficulty ? String(a.difficulty) : null,
    };
});

const result = computed(() => {
    const r = props.detail.result as Record<string, unknown>;
    return {
        artifact_id: r?.artifact_id ? String(r.artifact_id) : null,
        title: r?.title ? String(r.title) : null,
        error: r?.error ? String(r.error) : null,
    };
});

const displayTitle = computed(() => result.value.title || args.value.title || 'Visualization');

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
</script>

<template>
    <div class="space-y-5">
        <!-- Title + mode -->
        <div class="flex flex-wrap items-start justify-between gap-3">
            <p class="text-soft-silk text-[13px] font-semibold">{{ displayTitle }}</p>
            <div
                v-if="args.output_mode || args.difficulty"
                class="flex items-center gap-1.5 text-[11px]"
            >
                <span
                    v-if="args.output_mode"
                    class="rounded-md bg-amber-500/8 px-2 py-0.5 text-amber-300/80"
                >
                    {{ args.output_mode }}
                </span>
                <span
                    v-if="args.difficulty"
                    class="bg-stone-gray/8 text-stone-gray rounded-md px-2 py-0.5"
                >
                    {{ args.difficulty }}
                </span>
            </div>
        </div>

        <!-- Instructions -->
        <section v-if="args.instructions">
            <p class="text-stone-gray/60 mb-1 text-[11px] font-medium tracking-wider uppercase">
                Instructions
            </p>
            <p class="text-soft-silk/75 text-[13px] leading-relaxed">
                {{ args.instructions }}
            </p>
        </section>

        <!-- Artifacts -->
        <section v-if="extractedArtifacts.length">
            <UiChatUtilsSandboxArtifactsTray :artifacts="extractedArtifacts" />
        </section>

        <!-- Error -->
        <section v-if="result.error">
            <div
                class="flex items-start gap-3 rounded-lg border border-red-500/15 bg-red-500/[0.06]
                    p-3.5"
            >
                <UiIcon
                    name="MaterialSymbolsErrorCircleRounded"
                    class="mt-0.5 h-4 w-4 shrink-0 text-red-400"
                />
                <p class="text-[13px] leading-relaxed text-red-300">{{ result.error }}</p>
            </div>
        </section>
    </div>
</template>
