<script lang="ts" setup>
import type { Graph, Folder } from '@/types/graph';
import { ChromePicker } from 'vue-color';

// --- Props ---
const props = defineProps({
    folder: {
        type: Object as PropType<Folder & { graphs: Graph[]; color?: string }>,
        required: true,
    },
    isExpanded: {
        type: Boolean,
        required: true,
    },
    editingId: {
        type: String as PropType<string | null>,
        default: null,
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
        e: 'startRename' | 'startGraphRename' | 'deleteGraph' | 'updateFolderColor',
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

// --- Local State ---
const isPickerOpen = ref(false);
const color = ref(props.folder.color || 'rgba(255, 255, 255, 0.2)');

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

watch(
    () => color.value,
    () => {
        emit('updateFolderColor', props.folder.id, color.value || '');
    },
);
</script>

<template>
    <div>
        <div
            class="group border-stone-gray/10 flex w-full cursor-pointer items-center
                justify-between rounded-lg border py-1.5 pr-2 pl-4 transition-colors duration-200"
            :class="{
                'dark:bg-stone-gray/10 bg-obsidian/5 mb-2': isExpanded,
                'bg-stone-gray/5 hover:dark:bg-stone-gray/10 hover:bg-obsidian/5': !isExpanded,
            }"
            :style="
                folder.color ? { backgroundColor: folder.color, borderColor: folder.color } : {}
            "
            @click="emit('toggle', folder.id)"
        >
            <div class="flex min-w-0 grow items-center space-x-2 overflow-hidden">
                <UiIcon
                    name="MdiFolderOutline"
                    class="h-4 w-4 shrink-0 transition-transform duration-200"
                    :class="{
                        'text-ember-glow': isExpanded,
                        'text-stone-gray/80': !isExpanded,
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
                    class="rounded-full px-2 py-1 font-mono text-xs"
                    :class="[
                        folder.color
                            ? 'bg-black/20 text-white'
                            : 'text-stone-gray/50 bg-obsidian/20',
                    ]"
                >
                    {{ folder.graphs.length }}
                </div>
            </div>

            <!-- Action Menu -->
            <HeadlessMenu v-slot="{ open }" as="div" class="relative shrink-0">
                <HeadlessMenuButton
                    class="text-stone-gray/80 flex items-center justify-center rounded-md p-1
                        transition-all duration-200 hover:bg-black/10 hover:text-white
                        dark:hover:bg-white/10"
                    :class="{
                        'opacity-100': open,
                        'opacity-0 group-hover:opacity-100': !open,
                    }"
                    @click.stop
                >
                    <UiIcon name="Fa6SolidEllipsisVertical" class="h-5 w-5" />
                </HeadlessMenuButton>

                <transition
                    enter-active-class="transition ease-out duration-100"
                    enter-from-class="transform opacity-0 scale-95"
                    enter-to-class="transform opacity-100 scale-100"
                    leave-active-class="transition ease-in duration-75"
                    leave-from-class="transform opacity-100 scale-100"
                    leave-to-class="transform opacity-0 scale-95"
                >
                    <HeadlessMenuItems
                        class="dark:bg-stone-gray bg-anthracite dark:ring-anthracite/50
                            ring-stone-gray/10 absolute right-0 z-30 mt-2 w-60 origin-top-right
                            rounded-md p-1 shadow-lg ring-2 backdrop-blur-3xl focus:outline-none"
                        @click.stop
                    >
                        <!-- Rename -->
                        <HeadlessMenuItem v-slot="{ active }">
                            <button
                                class="group flex w-full items-center rounded-md px-2 py-2 text-sm
                                    font-bold"
                                :class="[
                                    active
                                        ? 'bg-obsidian/25 dark:text-obsidian text-soft-silk'
                                        : 'dark:text-obsidian text-soft-silk',
                                ]"
                                @click="emit('startRename', folder.id, folder.name)"
                            >
                                <UiIcon
                                    name="MaterialSymbolsEditRounded"
                                    class="mr-2 h-4 w-4"
                                    aria-hidden="true"
                                />
                                Rename
                            </button>
                        </HeadlessMenuItem>

                        <!-- Change Color -->
                        <div class="relative">
                            <HeadlessMenuItem>
                                <button
                                    class="group flex w-full items-center justify-between rounded-md
                                        px-2 py-2 text-sm font-bold"
                                    :class="[
                                        isPickerOpen
                                            ? 'bg-obsidian/25 dark:text-obsidian text-soft-silk'
                                            : `dark:text-obsidian text-soft-silk
                                                hover:bg-obsidian/25`,
                                    ]"
                                    @click.prevent="isPickerOpen = !isPickerOpen"
                                >
                                    <div class="flex items-center">
                                        <UiIcon
                                            name="MaterialSymbolsPaletteOutline"
                                            class="mr-2 h-4 w-4"
                                            aria-hidden="true"
                                        />
                                        Change Color
                                    </div>
                                    <div
                                        v-if="folder.color"
                                        class="h-3 w-3 rounded-full border border-white/20"
                                        :style="{ backgroundColor: folder.color }"
                                    />
                                </button>
                            </HeadlessMenuItem>
                        </div>

                        <!-- Color Picker Popover -->
                        <div v-if="isPickerOpen" class="mt-2 flex w-full justify-center">
                            <ChromePicker v-model="color" @click.stop />
                        </div>

                        <!-- Delete -->
                        <HeadlessMenuItem v-slot="{ active }">
                            <button
                                class="group flex w-full items-center rounded-md px-2 py-2 text-sm
                                    font-bold"
                                :class="[
                                    active
                                        ? 'bg-terracotta-clay/25 text-terracotta-clay'
                                        : 'text-terracotta-clay',
                                ]"
                                @click="emit('delete', folder.id)"
                            >
                                <UiIcon
                                    name="MaterialSymbolsDeleteRounded"
                                    class="mr-2 h-4 w-4"
                                    aria-hidden="true"
                                />
                                Delete
                            </button>
                        </HeadlessMenuItem>
                    </HeadlessMenuItems>
                </transition>
            </HeadlessMenu>
        </div>

        <div v-show="isExpanded" class="border-stone-gray/10 ml-2 space-y-2 border-l pl-2">
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
