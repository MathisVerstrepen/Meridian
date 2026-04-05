<script lang="ts" setup>
import type { PromptImproverRun } from '@/types/promptImprover';

defineProps<{
    currentRun: PromptImproverRun | null;
    workflowStep: number;
    workflowSteps: string[];
}>();

const emit = defineEmits<{
    close: [];
}>();
</script>

<template>
    <div
        class="border-stone-gray/10 flex items-center justify-between gap-4 border-b px-6 py-4"
    >
        <div class="flex min-w-0 items-center gap-5">
            <div class="flex min-w-0 flex-col">
                <h2 class="text-soft-silk text-lg font-bold tracking-tight">Prompt Improver</h2>
                <p class="text-stone-gray/50 text-[11px]">
                    Audit, improve, and apply dimension-aware prompt changes.
                </p>
            </div>

            <div v-if="currentRun" class="hidden items-center gap-1 sm:flex">
                <template v-for="(step, i) in workflowSteps" :key="step">
                    <div class="flex items-center gap-1.5">
                        <div
                            class="h-1.5 w-1.5 rounded-full transition-colors duration-300"
                            :class="
                                i < workflowStep
                                    ? 'bg-ember-glow'
                                    : i === workflowStep
                                      ? `bg-ember-glow shadow-ember-glow/50 shadow-[0_0_6px_1px]`
                                      : 'bg-white/10'
                            "
                        />
                        <span
                            class="text-[10px] font-semibold tracking-wider uppercase transition-colors duration-300"
                            :class="i <= workflowStep ? 'text-soft-silk/80' : 'text-stone-gray/30'"
                        >
                            {{ step }}
                        </span>
                    </div>
                    <div
                        v-if="i < workflowSteps.length - 1"
                        class="mx-1 h-px w-5 transition-colors duration-300"
                        :class="i < workflowStep ? 'bg-ember-glow/40' : 'bg-white/5'"
                    />
                </template>
            </div>
        </div>

        <button
            class="hover:bg-stone-gray/10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full transition-colors"
            aria-label="Close prompt improver"
            @click="emit('close')"
        >
            <UiIcon name="MaterialSymbolsClose" class="text-stone-gray h-5 w-5" />
        </button>
    </div>
</template>
