<script lang="ts" setup>
import type { Workspace } from '@/types/graph';

const props = defineProps<{
    workspaces: Workspace[];
    activeId: string | null;
}>();

const emit = defineEmits<{
    (e: 'select', id: string): void;
}>();

const containerRef = ref<HTMLElement | null>(null);

const scrollToActive = async () => {
    await nextTick();
    if (!containerRef.value || !props.activeId) return;

    const activeEl = containerRef.value.querySelector(`[data-id="${props.activeId}"]`);
    if (activeEl) {
        activeEl.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
    }
};

watch(() => props.activeId, scrollToActive);
onMounted(scrollToActive);
</script>

<template>
    <div
        v-if="workspaces.length > 1"
        class="absolute bottom-[4.2rem] left-0 z-10 flex h-8 w-full items-center justify-center
            pb-2"
    >
        <div
            ref="containerRef"
            class="hide-scrollbar flex max-w-[80%] items-center space-x-1 overflow-x-auto px-2"
            :class="[workspaces.length > 8 ? 'justify-start' : 'justify-center']"
        >
            <button
                v-for="ws in workspaces"
                :key="ws.id"
                :data-id="ws.id"
                class="group relative flex h-6 w-6 shrink-0 items-center justify-center"
                :title="ws.name"
                @click="emit('select', ws.id)"
            >
                <div
                    class="transition-all duration-300 ease-in-out"
                    :class="[
                        ws.id === activeId
                            ? 'bg-ember-glow h-2 w-2 rounded-full'
                            : `bg-stone-gray/30 group-hover:bg-stone-gray/60 h-1.5 w-1.5
                                rounded-full`,
                    ]"
                />
            </button>
        </div>
    </div>
</template>

<style scoped></style>
