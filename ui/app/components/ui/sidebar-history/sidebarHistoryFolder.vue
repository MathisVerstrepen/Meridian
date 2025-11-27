<script lang="ts" setup>
import type { Graph, Folder } from '@/types/graph';

// --- Props ---
const props = defineProps({
    folder: {
        type: Object as PropType<Folder & { graphs: Graph[] }>,
        required: true,
    },
    isExpanded: {
        type: Boolean,
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
    currentGraphId: {
        type: String as PropType<string | undefined>,
        required: true,
    },
    allFolders: {
        type: Array as PropType<Folder[]>,
        required: true,
    },
});

// --- Emits ---
const emit = defineEmits<{
    // Folder-specific actions
    (
        e: 'toggle' | 'update:editInputValue' | 'downloadGraph' | 'delete' | 'pinGraph',
        folderId: string,
    ): void;
    (
        e: 'startRename' | 'startGraphRename' | 'deleteGraph',
        folderId: string,
        folderName: string,
    ): void;

    // Generic input/rename actions
    (e: 'confirmRename' | 'cancelRename'): void;
    (e: 'setInputRef', id: string, el: unknown): void;

    // Bubbled events from child UiSidebarHistoryItem
    (e: 'navigate', graphId: string, temporary: boolean): void;
    (e: 'moveGraph', graphId: string, folderId: string | null): void;
}>();

// --- Computed ---
const isEditing = computed(() => props.folder.id === props.editingId);

// --- Handlers ---
const onInput = (event: Event) => {
    emit('update:editInputValue', (event.target as HTMLInputElement).value);
};

const onKeyDown = (event: KeyboardEvent) => {
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
    <div>
        <div
            class="group flex w-full cursor-pointer items-center justify-between rounded-lg py-1.5
                pr-2 pl-4 transition-colors duration-200"
            :class="{
                'dark:bg-stone-gray/10 bg-obsidian/5 mb-2': isExpanded,
                'bg-stone-gray/5 hover:dark:bg-stone-gray/10 hover:bg-obsidian/5': !isExpanded,
            }"
            @click="emit('toggle', folder.id)"
        >
            <div
                class="flex min-w-0 grow items-center space-x-2 overflow-hidden"
                @dblclick.stop="emit('startRename', folder.id, folder.name)"
            >
                <UiIcon
                    name="MdiFolderOutline"
                    class="h-4 w-4 shrink-0 transition-transform duration-200"
                    :class="{
                        'text-ember-glow': isExpanded,
                        'text-stone-gray/70': !isExpanded,
                    }"
                />
                <div v-if="isEditing" class="flex grow items-center">
                    <input
                        :ref="(el) => emit('setInputRef', folder.id, el)"
                        :value="editInputValue"
                        type="text"
                        class="bg-anthracite/20 text-stone-gray w-full rounded px-1 text-sm
                            font-bold outline-none"
                        @input="onInput"
                        @click.stop
                        @keydown="onKeyDown"
                        @blur="emit('confirmRename')"
                    />
                </div>
                <span v-else class="text-stone-gray truncate text-sm font-bold">
                    {{ folder.name }}
                </span>
                <div
                    class="text-stone-gray/50 bg-obsidian/20 rounded-full px-2 py-1 font-mono
                        text-xs"
                >
                    {{ folder.graphs.length }}
                </div>
            </div>

            <div class="opacity-0 transition-opacity group-hover:opacity-100">
                <button
                    class="hover:text-terracotta-clay text-stone-gray/50 flex items-center
                        justify-center px-1 py-2"
                    title="Delete Folder"
                    @click.stop="emit('delete', folder.id)"
                >
                    <UiIcon name="MaterialSymbolsDeleteRounded" class="h-4 w-4" />
                </button>
            </div>
        </div>

        <div v-show="isExpanded" class="border-stone-gray/10 ml-4 space-y-2 border-l pl-2">
            <div
                v-if="folder.graphs.length === 0"
                class="text-stone-gray/40 py-1 pl-2 text-xs italic"
            >
                Empty
            </div>
            <UiSidebarHistoryItem
                v-for="graph in folder.graphs"
                :key="graph.id"
                :graph="graph"
                :current-graph-id="currentGraphId"
                :editing-id="editingId"
                :edit-input-value="editInputValue"
                :folders="allFolders"
                @navigate="(graphId, temp) => emit('navigate', graphId, temp)"
                @start-rename="(graphId, graphName) => emit('startGraphRename', graphId, graphName)"
                @update:edit-input-value="(val) => emit('update:editInputValue', val)"
                @confirm-rename="emit('confirmRename')"
                @cancel-rename="emit('cancelRename')"
                @set-input-ref="(graphId, el) => emit('setInputRef', graphId, el)"
                @delete="(graphId, graphName) => emit('deleteGraph', graphId, graphName)"
                @download="(graphId) => emit('downloadGraph', graphId)"
                @pin="(graphId) => emit('pinGraph', graphId)"
                @move="(graphId, folderId) => emit('moveGraph', graphId, folderId)"
            />
        </div>
    </div>
</template>
