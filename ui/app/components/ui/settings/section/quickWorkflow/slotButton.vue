<script setup lang="ts">
import type { WheelSlot } from '@/types/settings';

defineProps<{
    slotData: WheelSlot;
    position: number;
    selected: boolean;
    state: 'empty' | 'configured' | 'invalid';
    tabIndex: 0 | -1;
    tabId: string;
    panelId: string;
    summary: string;
    summaryIcon?: string;
    summaryColor?: string;
}>();

defineEmits<{ activate: [] }>();
</script>

<template>
    <button
        :id="tabId"
        type="button"
        role="tab"
        :aria-selected="selected"
        :aria-controls="panelId"
        :tabindex="tabIndex"
        class="quick-workflow-control text-soft-silk hover:bg-stone-gray/8 focus-visible:ring-ember-glow relative min-w-0
            rounded-none border-0 bg-transparent px-3 py-3 text-left transition-colors focus-visible:z-10 focus-visible:ring-2
            focus-visible:ring-inset focus-visible:outline-none"
        :class="{
            'bg-ember-glow/10': selected,
        }"
        :aria-label="`${slotData.name || `Slot ${position}`}, ${summary}${state === 'invalid' ? ', needs repair' : ''}`"
        @click="$emit('activate')"
    >
        <span class="block min-w-0 truncate text-sm font-semibold">{{ slotData.name || `Slot ${position}` }}</span>
        <span class="text-stone-gray mt-1 flex min-w-0 items-center gap-1.5 text-xs">
            <UiIcon
                v-if="summaryIcon"
                :name="summaryIcon"
                class="h-4 w-4 shrink-0"
                :style="summaryIcon === 'MdiGithub' ? { color: 'var(--color-soft-silk)' } : { color: summaryColor }"
                :data-github-icon-contrast="summaryIcon === 'MdiGithub' ? 'settings-summary' : undefined"
                aria-hidden="true"
            />
            <span class="min-w-0 break-words">{{ summary }}</span>
        </span>
        <span v-if="state === 'invalid'" class="text-ember-glow mt-1 block text-xs font-semibold">
            Needs repair
        </span>
        <span v-else-if="state === 'configured'" class="text-stone-gray mt-1 block text-xs">Configured</span>
        <span v-else class="text-stone-gray mt-1 block text-xs">Empty</span>
        <span
            v-if="selected"
            aria-hidden="true"
            class="bg-ember-glow absolute right-0 -bottom-px left-0 h-0.5"
        />
    </button>
</template>
