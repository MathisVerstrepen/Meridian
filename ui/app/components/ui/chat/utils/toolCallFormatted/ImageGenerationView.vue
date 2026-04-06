<script setup lang="ts">
import type { ToolCallDetail } from '@/types/toolCall';

const props = defineProps<{
    detail: ToolCallDetail;
}>();

const args = computed(() => {
    const a = props.detail.arguments as Record<string, unknown>;
    return {
        prompt: String(a?.prompt || ''),
        aspect_ratio: a?.aspect_ratio ? String(a.aspect_ratio) : null,
        resolution: a?.resolution ? String(a.resolution) : null,
    };
});

const result = computed(() => {
    const r = props.detail.result as Record<string, unknown>;
    return {
        success: Boolean(r?.success),
        id: r?.id ? String(r.id) : null,
        prompt: r?.prompt ? String(r.prompt) : null,
        model: r?.model ? String(r.model) : null,
        error: r?.error ? String(r.error) : null,
    };
});

const imageUrl = computed(() => {
    if (!result.value.id) return null;
    return `/api/files/view/${result.value.id}`;
});

const hasParams = computed(
    () => result.value.model || args.value.aspect_ratio || args.value.resolution,
);
</script>

<template>
    <div class="space-y-5">
        <!-- Prompt -->
        <section>
            <p class="text-stone-gray/60 mb-1 text-[11px] font-medium uppercase tracking-wider">
                Prompt
            </p>
            <p class="text-soft-silk/85 text-[13px] leading-relaxed">
                {{ args.prompt }}
            </p>
        </section>

        <!-- Parameters -->
        <section v-if="hasParams">
            <div class="flex flex-wrap items-center gap-1.5 text-[11px]">
                <span
                    v-if="result.model"
                    class="bg-violet-500/8 text-violet-300/80 rounded-md px-2 py-0.5"
                >
                    {{ result.model }}
                </span>
                <span
                    v-if="args.aspect_ratio"
                    class="bg-stone-gray/8 text-stone-gray rounded-md px-2 py-0.5"
                >
                    {{ args.aspect_ratio }}
                </span>
                <span
                    v-if="args.resolution"
                    class="bg-stone-gray/8 text-stone-gray rounded-md px-2 py-0.5"
                >
                    {{ args.resolution }}
                </span>
            </div>
        </section>

        <!-- Image -->
        <section v-if="imageUrl">
            <UiChatUtilsGeneratedImageCard :prompt="args.prompt" :image-url="imageUrl" />
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
