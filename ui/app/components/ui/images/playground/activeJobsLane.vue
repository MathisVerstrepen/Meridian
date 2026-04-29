<script lang="ts" setup>
import type { ImageGenerationJob } from '@/types/imagePlayground';

defineProps<{
    jobs: ImageGenerationJob[];
    failedJobCount: number;
    modelDisplayName: (modelId?: string | null) => string;
}>();

const emit = defineEmits<{
    (e: 'retry', jobId: string): void;
    (e: 'dismiss', jobId: string): void;
    (e: 'cancel', jobId: string): void;
    (e: 'clearFailed'): void;
}>();
</script>

<template>
    <div v-if="jobs.length" class="mb-6">
        <div class="atelier-section-head mb-3">
            <span class="atelier-section-num text-ember-glow">·</span>
            <span class="atelier-section-label text-ember-glow/80">Active</span>
            <span class="atelier-section-rule bg-ember-glow/30" />
            <span class="text-ember-glow/80 ml-auto font-mono text-[10px] tabular-nums">
                {{ jobs.length }} active
            </span>
            <button
                v-if="failedJobCount"
                type="button"
                class="ml-2 rounded-full border border-red-400/25 bg-red-500/10 px-2 py-0.5
                    text-[9px] font-semibold tracking-wider text-red-200 uppercase transition
                    hover:bg-red-500/20"
                @click="emit('clearFailed')"
            >
                Clear {{ failedJobCount }} error{{ failedJobCount === 1 ? '' : 's' }}
            </button>
        </div>
        <div class="active-lane custom_scroll flex gap-3 overflow-x-auto pb-2">
            <div
                v-for="job in jobs"
                :key="job.id"
                class="bg-obsidian/60 active-card relative w-52 shrink-0 overflow-hidden rounded-2xl
                    border"
                :class="
                    job.status === 'failed'
                        ? 'border-red-400/45 bg-red-950/20'
                        : 'border-stone-gray/15'
                "
            >
                <div
                    class="developing-card group relative flex aspect-square items-center
                        justify-center overflow-hidden"
                    :class="{
                        'failed-card': job.status === 'failed',
                        'no-animation': job.status === 'failed',
                    }"
                >
                    <template v-if="job.status !== 'failed'">
                        <div class="developing-bath" />
                        <div class="developing-orb developing-orb-a" />
                        <div class="developing-orb developing-orb-b" />
                    </template>
                    <div class="relative z-10 flex flex-col items-center gap-2 px-3 text-center">
                        <div
                            v-if="job.status !== 'failed'"
                            class="developing-spinner border-soft-silk/15 border-t-ember-glow h-9
                                w-9 animate-spin rounded-full border-2"
                        />
                        <div
                            v-else
                            class="flex h-10 w-10 items-center justify-center rounded-xl
                                bg-red-500/15 text-red-200 ring-1 ring-red-300/25 ring-inset"
                        >
                            <UiIcon name="PhImageBroken" class="h-6 w-6" />
                        </div>
                        <span
                            class="font-mono text-[10px] tracking-widest uppercase"
                            :class="
                                job.status === 'failed' ? 'text-red-200/85' : 'text-soft-silk/80'
                            "
                        >
                            {{
                                job.status === 'failed'
                                    ? 'Failed'
                                    : job.status === 'retrying'
                                      ? 'Retrying'
                                      : job.status
                            }}
                        </span>
                        <span v-if="job.status === 'failed'" class="text-[10px] text-red-200/60">
                            {{ job.attempts }} / {{ job.max_attempts }} attempts
                        </span>
                    </div>
                    <button
                        v-if="job.status !== 'failed'"
                        type="button"
                        class="absolute top-2 right-2 z-20 flex h-7 w-7 items-center justify-center
                            rounded-full border border-red-300/25 bg-black/55 text-red-100 opacity-0
                            backdrop-blur transition group-hover:opacity-100 hover:border-red-300/55
                            hover:bg-red-500/20"
                        title="Cancel generation"
                        aria-label="Cancel generation"
                        @click.stop="emit('cancel', job.id)"
                    >
                        <UiIcon name="MaterialSymbolsClose" class="h-3.5 w-3.5" />
                    </button>
                </div>
                <div class="p-2.5">
                    <p class="text-soft-silk truncate text-[11px] font-semibold">
                        {{ job.prompt }}
                    </p>
                    <p class="text-stone-gray/70 mt-1 truncate text-[10px]">
                        {{ modelDisplayName(job.model) }}
                    </p>
                    <p
                        v-if="job.error"
                        class="mt-1.5 line-clamp-2 rounded-md border border-red-400/20 bg-red-500/10
                            p-1.5 text-[10px] leading-snug text-red-100/85"
                    >
                        {{ job.error }}
                    </p>
                    <div v-if="job.status === 'failed'" class="mt-2 grid grid-cols-2 gap-1.5">
                        <button
                            type="button"
                            class="rounded-lg border border-red-300/25 bg-red-500/10 px-2 py-1
                                text-[10px] font-semibold text-red-100 transition
                                hover:bg-red-500/20"
                            @click="emit('retry', job.id)"
                        >
                            Retry
                        </button>
                        <button
                            type="button"
                            class="border-stone-gray/15 text-stone-gray rounded-lg border
                                bg-black/20 px-2 py-1 text-[10px] font-semibold transition
                                hover:border-red-300/30 hover:text-red-100"
                            @click="emit('dismiss', job.id)"
                        >
                            Remove
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>
