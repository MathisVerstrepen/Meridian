<script lang="ts" setup>
import type { Workspace } from '@/types/graph';

defineProps<{
    workspaces: Workspace[];
    activeIndex: number;
}>();

const emit = defineEmits<{
    (e: 'select', index: number): void;
}>();
</script>

<template>
    <div
        v-if="workspaces.length > 1"
        class="absolute bottom-[4.2rem] left-0 z-10 flex h-8 w-full items-center justify-center
            space-x-1 pb-2"
    >
        <button
            v-for="(ws, index) in workspaces"
            :key="ws.id"
            class="group relative flex h-6 w-6 items-center justify-center"
            :title="ws.name"
            @click="emit('select', index)"
        >
            <div
                class="transition-all duration-300 ease-in-out"
                :class="[
                    index === activeIndex
                        ? 'bg-ember-glow h-2 w-2 rounded-full'
                        : 'bg-stone-gray/30 group-hover:bg-stone-gray/60 h-1.5 w-1.5 rounded-full',
                ]"
            />
        </button>
    </div>
</template>
