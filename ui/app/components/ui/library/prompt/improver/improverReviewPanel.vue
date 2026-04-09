<script lang="ts" setup>
import type { PromptImproverRun } from '@/types/promptImprover';

defineProps<{
    currentRun: PromptImproverRun;
    reviewStats: {
        accepted: number;
        rejected: number;
        pending: number;
        total: number;
    };
    canApply: boolean;
    isApplying: boolean;
    dimensionLookup: Map<string, { label: string; category: string; tier: number }>;
}>();

const emit = defineEmits<{
    apply: [];
    updateChangeReview: [changeId: string, reviewStatus: string];
}>();

const impactClass = (impact: string | null) => {
    switch ((impact || 'medium').toLowerCase()) {
        case 'high':
            return 'text-ember-glow bg-ember-glow/10';
        case 'medium':
            return 'text-cyan-300 bg-cyan-500/10';
        default:
            return 'text-deep-sea-teal bg-deep-sea-teal/10';
    }
};
</script>

<template>
    <div class="rounded-xl border border-white/5 bg-white/2 p-5">
        <div class="mb-4 flex items-center justify-between gap-3">
            <div class="flex min-w-0 flex-col gap-1">
                <span class="text-soft-silk text-sm font-semibold">Change Review</span>
                <div v-if="reviewStats.total > 0" class="flex items-center gap-2">
                    <span
                        v-if="reviewStats.accepted"
                        class="flex items-center gap-1 text-[10px] text-emerald-400/70"
                    >
                        <span class="h-1 w-1 rounded-full bg-emerald-400" />
                        {{ reviewStats.accepted }} accepted
                    </span>
                    <span
                        v-if="reviewStats.rejected"
                        class="flex items-center gap-1 text-[10px] text-rose-400/70"
                    >
                        <span class="h-1 w-1 rounded-full bg-rose-400" />
                        {{ reviewStats.rejected }} rejected
                    </span>
                    <span
                        v-if="reviewStats.pending"
                        class="text-stone-gray/40 flex items-center gap-1 text-[10px]"
                    >
                        <span class="bg-stone-gray/40 h-1 w-1 rounded-full" />
                        {{ reviewStats.pending }} pending
                    </span>
                </div>
            </div>
            <button
                class="bg-ember-glow text-obsidian group hover:shadow-ember-glow/20 relative shrink-0 overflow-hidden rounded-lg px-4 py-2 text-xs font-bold transition-all duration-200 hover:shadow-lg disabled:opacity-40 disabled:shadow-none"
                :disabled="!canApply"
                @click="emit('apply')"
            >
                <span class="relative z-10">{{ isApplying ? 'Applying…' : 'Apply To Node' }}</span>
                <div
                    v-if="!isApplying && canApply"
                    class="absolute inset-0 -translate-x-full bg-linear-to-r from-transparent via-white/20 to-transparent group-hover:animate-[shimmer_1.5s_ease-in-out]"
                />
            </button>
        </div>

        <div
            v-if="!currentRun.changes.length"
            class="text-stone-gray/40 rounded-lg border border-white/5 bg-black/10 px-4 py-8 text-center text-xs"
        >
            <p>No diff clusters generated.</p>
            <p class="text-stone-gray/25 mt-1">
                The prompt may already match the target profile, or improvement hasn't been run yet.
            </p>
        </div>

        <div v-else class="space-y-3">
            <div
                v-for="(change, changeIndex) in currentRun.changes"
                :key="change.id"
                class="change-card rounded-xl border border-white/5 bg-black/15 p-4 transition-colors duration-200"
                :class="
                    change.reviewStatus === 'accepted'
                        ? 'border-emerald-500/10'
                        : change.reviewStatus === 'rejected'
                          ? 'border-rose-500/10 opacity-60'
                          : ''
                "
                :style="{ animationDelay: changeIndex * 50 + 'ms' }"
            >
                <div class="mb-3 flex items-start justify-between gap-3">
                    <div class="min-w-0">
                        <p class="text-soft-silk/90 text-[13px] leading-tight font-semibold">
                            {{ change.title || 'Prompt improvement' }}
                        </p>
                        <div class="mt-1 flex flex-wrap items-center gap-1.5">
                            <span class="text-stone-gray/50 text-[10px]">
                                {{
                                    change.dimensionId
                                        ? dimensionLookup.get(change.dimensionId)?.label || change.dimensionId
                                        : 'General'
                                }}
                            </span>
                            <span
                                class="rounded-full px-1.5 py-0.5 text-[9px] font-semibold tracking-wider uppercase"
                                :class="impactClass(change.impact)"
                            >
                                {{ change.impact || 'Medium' }}
                            </span>
                        </div>
                    </div>

                    <div class="flex shrink-0 overflow-hidden rounded-lg border border-white/5">
                        <button
                            class="px-2.5 py-1.5 text-[10px] font-bold tracking-wider uppercase transition-all duration-150"
                            :class="
                                change.reviewStatus === 'accepted'
                                    ? `bg-emerald-500/20 text-emerald-300`
                                    : `text-stone-gray/40 hover:text-stone-gray/70 bg-white/3`
                            "
                            @click="emit('updateChangeReview', change.id, 'accepted')"
                        >
                            Accept
                        </button>
                        <div class="w-px bg-white/5" />
                        <button
                            class="px-2.5 py-1.5 text-[10px] font-bold tracking-wider uppercase transition-all duration-150"
                            :class="
                                change.reviewStatus === 'rejected'
                                    ? `bg-rose-500/20 text-rose-300`
                                    : `text-stone-gray/40 hover:text-stone-gray/70 bg-white/3`
                            "
                            @click="emit('updateChangeReview', change.id, 'rejected')"
                        >
                            Reject
                        </button>
                    </div>
                </div>

                <p v-if="change.rationale" class="text-stone-gray/50 mb-3 text-[11px] leading-relaxed">
                    {{ change.rationale }}
                </p>

                <div class="grid gap-2 md:grid-cols-2">
                    <div>
                        <p class="text-stone-gray/30 mb-1 text-[9px] font-bold tracking-wider uppercase">
                            Original
                        </p>
                        <pre
                            class="dark-scrollbar max-h-40 overflow-auto rounded-lg border border-rose-500/8 bg-rose-500/3 p-3 text-[11px] leading-relaxed whitespace-pre-wrap text-rose-200/60"
                        >{{ change.sourceText || '[Insert]' }}</pre>
                    </div>
                    <div>
                        <p class="text-stone-gray/30 mb-1 text-[9px] font-bold tracking-wider uppercase">
                            Suggested
                        </p>
                        <pre
                            class="dark-scrollbar max-h-40 overflow-auto rounded-lg border border-emerald-500/8 bg-emerald-500/3 p-3 text-[11px] leading-relaxed whitespace-pre-wrap text-emerald-200/70"
                        >{{ change.suggestedText || '[Delete]' }}</pre>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.change-card {
    animation: change-card-in 0.3s cubic-bezier(0.16, 1, 0.3, 1) both;
}

@keyframes change-card-in {
    from {
        opacity: 0;
        transform: translateY(6px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

@keyframes shimmer {
    to {
        transform: translateX(200%);
    }
}
</style>
