<script lang="ts" setup>
import { onClickOutside } from '@vueuse/core';
import { AnimatePresence, motion } from 'motion-v';

defineProps<{
    breadcrumbs: FileSystemObject[];
    searchQuery: string;
    viewMode: ViewMode;
    sortBy: SortOption;
    sortDirection: SortDirection;
    canGoBack: boolean;
    canGoForward: boolean;
    selectedCount: number;
    selectedDownloadCount: number;
    selectedMovableCount: number;
    isUserUploadsTab: boolean;
    isCreatingFolder: boolean;
    newFolderName: string;
    isStorageFull: boolean;
}>();

const emit = defineEmits<{
    (e: 'navigate', folder: FileSystemObject): void;
    (e: 'goBack'): void;
    (e: 'goForward'): void;
    (e: 'update:searchQuery', query: string): void;
    (e: 'toggleViewMode', mode: ViewMode): void;
    (e: 'update:sortBy', sort: SortOption): void;
    (e: 'update:sortDirection', dir: SortDirection): void;
    (e: 'deleteSelected'): void;
    (e: 'downloadSelected'): void;
    (e: 'moveSelected'): void;
    (e: 'copySelected'): void;
    (e: 'update:isCreatingFolder', val: boolean): void;
    (e: 'update:newFolderName', val: string): void;
    (e: 'createFolder'): void;
    (e: 'triggerUpload'): void;
    (e: 'triggerFolderUpload'): void;
}>();

const searchInputRef = useTemplateRef<HTMLInputElement>('searchInputRef');
const jumpMenuRef = useTemplateRef<HTMLElement>('jumpMenuRef');
const jumpMenuPosition = ref({ top: 0, left: 0 });
const isJumpMenuOpen = ref(false);

onClickOutside(jumpMenuRef, () => {
    isJumpMenuOpen.value = false;
});

const focusSearchInput = () => {
    searchInputRef.value?.focus();
};

const openJumpMenu = (event: MouseEvent) => {
    const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
    jumpMenuPosition.value = {
        top: rect.bottom + 6,
        left: rect.left,
    };
    isJumpMenuOpen.value = true;
};

const jumpToFolder = (folder: FileSystemObject) => {
    isJumpMenuOpen.value = false;
    emit('navigate', folder);
};

defineExpose({ focusSearchInput });
</script>

<template>
    <div class="flex flex-col gap-3">
        <!-- Row 1: Breadcrumbs + Search -->
        <div class="flex items-center justify-between gap-4">
            <!-- Breadcrumbs -->
            <div class="flex min-h-[36px] min-w-0 flex-1 items-center gap-1 overflow-hidden text-sm">
                <template v-if="isUserUploadsTab">
                    <div class="mr-2 flex shrink-0 items-center gap-1">
                        <button
                            class="bg-stone-gray/10 hover:bg-stone-gray/20 text-soft-silk flex h-9 w-9
                                items-center justify-center rounded-lg transition-colors duration-200
                                ease-in-out disabled:cursor-not-allowed disabled:opacity-50"
                            title="Back"
                            :disabled="!canGoBack"
                            @click="emit('goBack')"
                        >
                            <UiIcon name="LineMdChevronSmallUp" class="h-5 w-5 -rotate-90" />
                        </button>
                        <button
                            class="bg-stone-gray/10 hover:bg-stone-gray/20 text-soft-silk flex h-9 w-9
                                items-center justify-center rounded-lg transition-colors duration-200
                                ease-in-out disabled:cursor-not-allowed disabled:opacity-50"
                            title="Forward"
                            :disabled="!canGoForward"
                            @click="emit('goForward')"
                        >
                            <UiIcon name="LineMdChevronSmallUp" class="h-5 w-5 rotate-90" />
                        </button>
                    </div>
                    <span
                        v-for="(part, index) in breadcrumbs"
                        :key="part.id"
                        class="text-stone-gray/60 flex min-w-0 items-center gap-1"
                    >
                        <button
                            v-if="index > 0"
                            class="hover:bg-stone-gray/10 text-stone-gray/40 shrink-0 rounded px-1
                                transition-colors hover:text-soft-silk"
                            title="Jump to folder"
                            @click.stop="openJumpMenu"
                        >
                            /
                        </button>
                        <button
                            class="hover:text-soft-silk truncate transition-colors"
                            :disabled="index === breadcrumbs.length - 1"
                            @click="emit('navigate', part)"
                        >
                            {{ part.name === '/' ? 'Root' : part.name }}
                        </button>
                    </span>

                    <Teleport to="body">
                        <div
                            v-if="isJumpMenuOpen"
                            ref="jumpMenuRef"
                            class="bg-obsidian border-stone-gray/20 text-soft-silk fixed z-100 flex
                                min-w-44 flex-col rounded-lg border py-1 shadow-xl backdrop-blur-md"
                            :style="{
                                top: `${jumpMenuPosition.top}px`,
                                left: `${jumpMenuPosition.left}px`,
                            }"
                            @contextmenu.prevent
                        >
                            <p class="text-stone-gray/50 px-3 py-1.5 text-xs font-medium">
                                Jump to
                            </p>
                            <button
                                v-for="folder in breadcrumbs.slice(0, -1)"
                                :key="folder.id"
                                class="hover:bg-stone-gray/10 flex w-full items-center gap-2 px-3 py-1.5
                                    text-left text-sm"
                                @click="jumpToFolder(folder)"
                            >
                                <UiIcon name="MdiFolderOutline" class="h-4 w-4 shrink-0" />
                                <span class="truncate">
                                    {{ folder.name === '/' ? 'Root' : folder.name }}
                                </span>
                            </button>
                        </div>
                    </Teleport>
                </template>
                <template v-else>
                    <span class="text-soft-silk font-medium">Generated Images</span>
                </template>
            </div>

            <!-- Search -->
            <div class="relative w-full max-w-xs shrink-0">
                <UiIcon
                    name="MdiMagnify"
                    class="text-stone-gray/60 pointer-events-none absolute top-1/2 left-3 h-4 w-4
                        -translate-y-1/2"
                />
                <input
                    ref="searchInputRef"
                    :value="searchQuery"
                    type="text"
                    :placeholder="
                        isUserUploadsTab ? 'Search current folder...' : 'Search generated images...'
                    "
                    class="bg-obsidian border-stone-gray/20 text-soft-silk focus:border-ember-glow
                        h-9 w-full rounded-lg border py-2 pr-8 pl-9 text-sm focus:outline-none"
                    @input="emit('update:searchQuery', ($event.target as HTMLInputElement).value)"
                />
                <button
                    v-if="searchQuery"
                    class="text-stone-gray/60 hover:text-soft-silk absolute top-1/2 right-2 flex h-6
                        w-6 -translate-y-1/2 items-center justify-center rounded-md
                        transition-colors"
                    @click="emit('update:searchQuery', '')"
                >
                    <UiIcon name="MaterialSymbolsClose" class="h-4 w-4" />
                </button>
            </div>
        </div>

        <!-- Row 2: View + Sort | Bulk Actions | Upload -->
        <div class="flex flex-wrap items-center justify-between gap-2">
            <!-- Left: View + Sort -->
            <div class="flex items-center gap-2">
                <!-- View Mode Toggles -->
                <div class="bg-stone-gray/10 flex items-center rounded-lg p-0.5">
                    <button
                        v-for="mode in ['gallery', 'grid', 'list'] as const"
                        :key="mode"
                        class="flex h-7 w-7 items-center justify-center rounded transition-all"
                        :class="
                            viewMode === mode
                                ? 'bg-stone-gray/20 text-soft-silk'
                                : 'text-stone-gray/50 hover:text-stone-gray/80'
                        "
                        :title="mode.charAt(0).toUpperCase() + mode.slice(1) + ' View'"
                        @click="emit('toggleViewMode', mode)"
                    >
                        <UiIcon
                            :name="
                                mode === 'gallery'
                                    ? 'MdiViewGridOutline'
                                    : mode === 'grid'
                                      ? 'MdiViewGridCompact'
                                      : 'MdiViewListOutline'
                            "
                            class="h-4 w-4"
                        />
                    </button>
                </div>

                <div class="bg-stone-gray/20 h-5 w-px" />

                <!-- Sorting -->
                <div class="text-stone-gray/60 flex shrink-0 items-center gap-1 text-sm">
                    <span>Sort by:</span>
                    <button
                        class="rounded px-2 py-0.5 font-medium transition-colors"
                        :class="
                            sortBy === 'name'
                                ? 'text-soft-silk bg-stone-gray/20'
                                : 'hover:bg-stone-gray/10'
                        "
                        @click="emit('update:sortBy', 'name')"
                    >
                        Name
                    </button>
                    <button
                        class="rounded px-2 py-0.5 font-medium transition-colors"
                        :class="
                            sortBy === 'date'
                                ? 'text-soft-silk bg-stone-gray/20'
                                : 'hover:bg-stone-gray/10'
                        "
                        @click="emit('update:sortBy', 'date')"
                    >
                        Date
                    </button>
                    <button
                        class="hover:bg-stone-gray/10 rounded p-1 transition-colors"
                        title="Toggle sort direction"
                        @click="emit('update:sortDirection', sortDirection === 'asc' ? 'desc' : 'asc')"
                    >
                        <UiIcon
                            :name="'MdiArrowUp'"
                            class="h-4 w-4 transition-transform duration-200 ease-in-out"
                            :class="{ 'rotate-180': sortDirection === 'desc' }"
                        />
                    </button>
                </div>
            </div>

            <!-- Right: Bulk Actions + Upload -->
            <div class="flex items-center gap-2">
                <!-- Bulk Actions -->
                <Transition name="bulk-actions">
                    <div
                        v-if="selectedCount > 0"
                        class="bg-stone-gray/10 text-stone-gray/70 flex shrink-0 items-center gap-1
                            rounded-lg px-2 py-1 text-xs"
                    >
                        <span class="text-soft-silk mr-1 font-medium">{{ selectedCount }} selected</span>
                        <button
                            class="hover:bg-stone-gray/10 rounded px-2 py-1 transition-colors
                                disabled:cursor-not-allowed disabled:opacity-40"
                            :disabled="selectedDownloadCount === 0"
                            title="Download selected files"
                            @click="emit('downloadSelected')"
                        >
                            Download
                        </button>
                        <button
                            v-if="isUserUploadsTab"
                            class="hover:bg-stone-gray/10 rounded px-2 py-1 transition-colors
                                disabled:cursor-not-allowed disabled:opacity-40"
                            :disabled="selectedMovableCount === 0"
                            title="Move selected files"
                            @click="emit('moveSelected')"
                        >
                            Move
                        </button>
                        <button
                            v-if="isUserUploadsTab"
                            class="hover:bg-stone-gray/10 rounded px-2 py-1 transition-colors
                                disabled:cursor-not-allowed disabled:opacity-40"
                            :disabled="selectedMovableCount === 0 || isStorageFull"
                            title="Copy selected files"
                            @click="emit('copySelected')"
                        >
                            Copy
                        </button>
                        <button
                            class="rounded px-2 py-1 text-red-400 transition-colors hover:bg-red-500/10"
                            title="Delete selected files"
                            @click="emit('deleteSelected')"
                        >
                            Delete
                        </button>
                    </div>
                </Transition>

                <!-- Upload Controls -->
                <template v-if="isUserUploadsTab">
                    <div class="bg-stone-gray/20 h-5 w-px" />

                    <AnimatePresence>
                        <motion.div
                            v-if="isCreatingFolder"
                            :initial="{ width: 0, opacity: 0 }"
                            :animate="{ width: 'auto', opacity: 1 }"
                            :exit="{ width: 0, opacity: 0 }"
                            class="shrink-0 overflow-hidden"
                        >
                            <input
                                :value="newFolderName"
                                type="text"
                                placeholder="Folder name..."
                                class="bg-obsidian border-stone-gray/20 text-soft-silk
                                    focus:border-ember-glow h-9 w-48 rounded-lg border px-3 text-sm
                                    focus:outline-none"
                                @input="
                                    emit(
                                        'update:newFolderName',
                                        ($event.target as HTMLInputElement).value,
                                    )
                                "
                                @keyup.enter="emit('createFolder')"
                                @keyup.esc="emit('update:isCreatingFolder', false)"
                            />
                        </motion.div>
                    </AnimatePresence>

                    <button
                        class="bg-stone-gray/10 hover:bg-stone-gray/20 text-soft-silk flex h-9 w-9
                            shrink-0 items-center justify-center rounded-lg transition-colors"
                        title="New Folder"
                        @click="emit('update:isCreatingFolder', !isCreatingFolder)"
                    >
                        <UiIcon name="MdiFolderPlusOutline" class="h-5 w-5" />
                    </button>

                    <button
                        class="bg-stone-gray/10 hover:bg-stone-gray/20 text-soft-silk flex h-9 w-9
                            shrink-0 items-center justify-center rounded-lg transition-colors
                            disabled:cursor-not-allowed disabled:opacity-50"
                        title="Upload Folder"
                        :disabled="isStorageFull"
                        @click="emit('triggerFolderUpload')"
                    >
                        <UiIcon name="MdiFolderUploadOutline" class="h-5 w-5" />
                    </button>

                    <button
                        class="bg-stone-gray/10 hover:bg-stone-gray/20 text-soft-silk flex h-9 w-9
                            shrink-0 items-center justify-center rounded-lg transition-colors
                            disabled:cursor-not-allowed disabled:opacity-50"
                        title="Upload File"
                        :disabled="isStorageFull"
                        @click="emit('triggerUpload')"
                    >
                        <UiIcon name="UilUpload" class="h-5 w-5" />
                    </button>
                </template>
            </div>
        </div>
    </div>
</template>

<style scoped>
.bulk-actions-enter-active,
.bulk-actions-leave-active {
    transition:
        opacity 0.2s ease,
        transform 0.2s ease;
}
.bulk-actions-enter-from,
.bulk-actions-leave-to {
    opacity: 0;
    transform: translateX(8px);
}
</style>
