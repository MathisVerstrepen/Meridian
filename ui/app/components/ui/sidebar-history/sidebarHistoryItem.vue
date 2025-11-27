<script lang="ts" setup>
import type { Graph, Folder } from '@/types/graph';

const props = defineProps({
    graph: {
        type: Object as PropType<Graph>,
        required: true,
    },
    currentGraphId: {
        type: String as PropType<string | undefined>,
        required: true,
    },
    editingId: {
        type: String as PropType<string | null>,
        required: true,
    },
    editInputValue: {
        type: String,
        required: true,
    },
    folders: {
        type: Array as PropType<Folder[]>,
        required: true,
    },
});

const emit = defineEmits<{
    (e: 'navigate', graphId: string, temporary: boolean): void;
    (e: 'startRename' | 'delete', graphId: string, graphName: string): void;
    (e: 'update:editInputValue' | 'pin' | 'download', value: string): void;
    (e: 'confirmRename' | 'cancelRename'): void;
    (e: 'move', graphId: string, folderId: string | null): void;
    (e: 'setInputRef', graphId: string, el: unknown): void;
}>();

const isCurrent = computed(() => props.graph.id === props.currentGraphId);
const isEditing = computed(() => props.graph.id === props.editingId);

const onInput = (event: Event) => {
    emit('update:editInputValue', (event.target as HTMLInputElement).value);
};

const handleKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'Enter') {
        event.preventDefault();
        emit('confirmRename');
    }
    if (event.key === 'Escape') {
        event.preventDefault();
        emit('cancelRename');
    }
};
</script>

<template>
    <div
        class="group flex w-full max-w-full cursor-pointer items-center justify-between rounded-lg
            py-1.5 pr-2 pl-4 transition-colors duration-300 ease-in-out"
        :class="{
            'dark:bg-obsidian bg-soft-silk dark:text-stone-gray text-obsidian': isCurrent,
            [`dark:bg-stone-gray dark:hover:bg-stone-gray/80 dark:text-obsidian bg-obsidian
            text-soft-silk/80`]: !isCurrent,
        }"
        @click="emit('navigate', graph.id, false)"
    >
        <div
            class="flex h-6 min-w-0 grow-1 items-center space-x-2 overflow-hidden"
            @dblclick.stop="emit('startRename', graph.id, graph.name)"
        >
            <div
                v-if="isCurrent && !isEditing && !graph.pinned"
                class="bg-ember-glow/80 mr-2 h-2 w-4 shrink-0 rounded-full"
            />
            <UiIcon
                v-if="graph.pinned && !isEditing"
                name="MajesticonsPin"
                class="h-4 w-4 shrink-0"
                :class="[isCurrent ? 'text-ember-glow/80' : 'text-obsidian']"
            />

            <div v-if="isEditing" class="flex w-full items-center space-x-2">
                <UiIcon
                    name="MaterialSymbolsEditRounded"
                    class="text-ember-glow/80 h-4 w-4"
                    aria-hidden="true"
                />
                <input
                    :ref="(el) => emit('setInputRef', graph.id, el)"
                    :value="editInputValue"
                    type="text"
                    class="w-full rounded px-2 font-bold outline-none"
                    :class="[isCurrent ? 'bg-stone-gray/20' : 'bg-anthracite/20']"
                    @input="onInput"
                    @click.stop
                    @keydown="handleKeyDown"
                    @blur="emit('confirmRename')"
                />
            </div>

            <span v-else class="truncate font-bold" :title="graph.name">
                {{ graph.name }}
            </span>
        </div>

        <UiSidebarHistoryActions
            :graph="graph"
            :current-graph-id="currentGraphId"
            :folders="folders"
            @rename="(id: string) => emit('startRename', id, graph.name)"
            @delete="(id: string, name: string) => emit('delete', id, name)"
            @download="(id: string) => emit('download', id)"
            @pin="(id: string) => emit('pin', id)"
            @move="(graphId: string, folderId: string | null) => emit('move', graphId, folderId)"
        />
    </div>
</template>
