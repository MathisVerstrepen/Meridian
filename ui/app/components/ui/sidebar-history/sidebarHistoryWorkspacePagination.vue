<script lang="ts" setup>
import type { Workspace } from '@/types/graph';

defineProps<{
    workspaces: Workspace[];
    activeId: string | null;
}>();

const emit = defineEmits<{
    (e: 'select', id: string): void;
}>();
</script>

<template>
    <div
        v-if="workspaces.length > 1"
        class="mt-3 mb-2 shrink-0"
    >
        <div
            role="group"
            aria-label="Workspaces"
            class="flex w-full items-center gap-2"
            @wheel.stop
        >
            <button
                v-for="ws in workspaces"
                :key="ws.id"
                :data-id="ws.id"
                type="button"
                :aria-pressed="ws.id === activeId"
                class="focus-visible:ring-ember-glow flex h-9 min-w-0 flex-1 cursor-pointer
                    items-center justify-center rounded-lg border px-3 text-sm font-semibold
                    transition-colors
                    focus-visible:ring-2 focus-visible:ring-inset focus-visible:outline-none"
                :class="
                    ws.id === activeId
                        ? 'border-ember-glow/40 bg-ember-glow/15 text-ember-glow'
                        : 'border-transparent bg-stone-gray/5 text-stone-gray/70 hover:bg-stone-gray/10 hover:text-stone-gray'
                "
                :title="ws.name"
                @click="emit('select', ws.id)"
            >
                <span class="truncate">{{ ws.name }}</span>
            </button>
        </div>
    </div>
</template>
