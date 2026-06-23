<script lang="ts" setup>
import { onClickOutside } from '@vueuse/core';
import { AnimatePresence, motion } from 'motion-v';

const props = defineProps<{
    breadcrumbs: FileSystemObject[];
    searchQuery: string;
    viewMode: ViewMode;
    sortBy: SortOption;
    sortDirection: SortDirection;
    fileTypeFilter: FileTypeFilter;
    foldersFirst: boolean;
    searchScope: FileSearchScope;
    canGoBack: boolean;
    canGoForward: boolean;
    selectedCount: number;
    selectedDownloadCount: number;
    selectedMovableCount: number;
    isUserUploadsTab: boolean;
    isGoogleDriveTab: boolean;
    isCreatingFolder: boolean;
    newFolderName: string;
    isStorageFull: boolean;
    isAllUploadsLoading: boolean;
    isDragMoveActive?: boolean;
    dragMoveTargetId?: string | null;
}>();

const emit = defineEmits<{
    (e: 'navigate', folder: FileSystemObject): void;
    (e: 'goBack'): void;
    (e: 'goForward'): void;
    (e: 'update:searchQuery', query: string): void;
    (e: 'toggleViewMode', mode: ViewMode): void;
    (e: 'update:sortBy', sort: SortOption): void;
    (e: 'update:sortDirection', dir: SortDirection): void;
    (e: 'update:fileTypeFilter', filter: FileTypeFilter): void;
    (e: 'update:foldersFirst', value: boolean): void;
    (e: 'update:searchScope', scope: FileSearchScope): void;
    (e: 'deleteSelected'): void;
    (e: 'downloadSelected'): void;
    (e: 'moveSelected'): void;
    (e: 'copySelected'): void;
    (e: 'update:isCreatingFolder', val: boolean): void;
    (e: 'update:newFolderName', val: string): void;
    (e: 'createFolder'): void;
    (e: 'triggerUpload'): void;
    (e: 'triggerFolderUpload'): void;
    (e: 'dragMoveOver', event: DragEvent, folder: FileSystemObject): void;
    (e: 'dragMoveLeave', event: DragEvent, folder: FileSystemObject): void;
    (e: 'dragMoveDrop', event: DragEvent, folder: FileSystemObject): void;
}>();

const searchInputRef = useTemplateRef<HTMLInputElement>('searchInputRef');
const jumpMenuRef = useTemplateRef<HTMLElement>('jumpMenuRef');
const sortMenuRef = useTemplateRef<HTMLElement>('sortMenuRef');
const jumpMenuPosition = ref({ top: 0, left: 0 });
const isJumpMenuOpen = ref(false);
const isSortMenuOpen = ref(false);

const fileTypeOptions: { value: FileTypeFilter; label: string }[] = [
    { value: 'all', label: 'All types' },
    { value: 'images', label: 'Images' },
    { value: 'pdfs', label: 'PDFs' },
    { value: 'text', label: 'Text' },
    { value: 'folders', label: 'Folders' },
];

const sortOptions: { value: SortOption; label: string }[] = [
    { value: 'name', label: 'Name' },
    { value: 'date', label: 'Date' },
    { value: 'size', label: 'Size' },
    { value: 'type', label: 'Type' },
];

const currentSortLabel = computed(
    () => sortOptions.find((opt) => opt.value === props.sortBy)?.label ?? 'Name',
);

onClickOutside(jumpMenuRef, () => {
    isJumpMenuOpen.value = false;
});

onClickOutside(sortMenuRef, () => {
    isSortMenuOpen.value = false;
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

const selectSort = (sort: SortOption) => {
    emit('update:sortBy', sort);
    isSortMenuOpen.value = false;
};

const toggleSortMenu = (event: MouseEvent) => {
    event.stopPropagation();
    isSortMenuOpen.value = !isSortMenuOpen.value;
};

const handleBreadcrumbDragOver = (event: DragEvent, folder: FileSystemObject) => {
    if (!props.isDragMoveActive) return;
    event.preventDefault();
    emit('dragMoveOver', event, folder);
};

const handleBreadcrumbDrop = (event: DragEvent, folder: FileSystemObject) => {
    if (!props.isDragMoveActive) return;
    event.preventDefault();
    emit('dragMoveDrop', event, folder);
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
                    <div class="mr-1 flex shrink-0 items-center gap-1">
                        <button
                            class="bg-stone-gray/10 hover:bg-stone-gray/20 text-soft-silk flex h-8 w-8
                                items-center justify-center rounded-lg transition-colors duration-200
                                disabled:cursor-not-allowed disabled:opacity-40"
                            title="Back (Alt+←)"
                            :disabled="!canGoBack"
                            @click="emit('goBack')"
                        >
                            <UiIcon name="LineMdChevronSmallUp" class="h-4 w-4 -rotate-90" />
                        </button>
                        <button
                            class="bg-stone-gray/10 hover:bg-stone-gray/20 text-soft-silk flex h-8 w-8
                                items-center justify-center rounded-lg transition-colors duration-200
                                disabled:cursor-not-allowed disabled:opacity-40"
                            title="Forward (Alt+→)"
                            :disabled="!canGoForward"
                            @click="emit('goForward')"
                        >
                            <UiIcon name="LineMdChevronSmallUp" class="h-4 w-4 rotate-90" />
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
                            :class="[
                                index === breadcrumbs.length - 1 ? 'text-soft-silk font-medium' : '',
                                dragMoveTargetId === part.id
                                    ? 'bg-ember-glow/10 text-ember-glow ring-ember-glow/40 rounded px-1 ring-1'
                                    : '',
                            ]"
                            :disabled="index === breadcrumbs.length - 1 && !isDragMoveActive"
                            @click="index !== breadcrumbs.length - 1 && emit('navigate', part)"
                            @dragover="handleBreadcrumbDragOver($event, part)"
                            @dragleave="emit('dragMoveLeave', $event, part)"
                            @drop="handleBreadcrumbDrop($event, part)"
                        >
                            {{ part.name === '/' ? 'Root' : part.name }}
                        </button>
                    </span>

                    <Teleport to="body">
                        <div
                            v-if="isJumpMenuOpen"
                            ref="jumpMenuRef"
                            class="bg-obsidian/95 border-stone-gray/20 text-soft-silk fixed z-100 flex
                                min-w-44 flex-col rounded-xl border py-1 shadow-2xl backdrop-blur-md"
                            :style="{
                                top: `${jumpMenuPosition.top}px`,
                                left: `${jumpMenuPosition.left}px`,
                            }"
                            @contextmenu.prevent
                        >
                            <p class="text-stone-gray/50 px-3 py-1.5 text-xs font-medium uppercase tracking-wide">
                                Jump to
                            </p>
                            <button
                                v-for="folder in breadcrumbs.slice(0, -1)"
                                :key="folder.id"
                                class="hover:bg-stone-gray/10 flex w-full items-center gap-2 px-3 py-1.5
                                    text-left text-sm transition-colors"
                                @click="jumpToFolder(folder)"
                            >
                                <UiIcon name="MdiFolderOutline" class="h-4 w-4 shrink-0 text-stone-gray/70" />
                                <span class="truncate">
                                    {{ folder.name === '/' ? 'Root' : folder.name }}
                                </span>
                            </button>
                        </div>
                    </Teleport>
                </template>
                <template v-else-if="isGoogleDriveTab">
                    <UiIcon name="CiGoogle" class="text-ember-glow/60 mr-1 h-5 w-5 shrink-0" />
                    <span class="text-soft-silk font-medium">Google Drive</span>
                </template>
                <template v-else>
                    <UiIcon name="MynauiSparklesSolid" class="text-ember-glow/60 mr-1 h-5 w-5 shrink-0" />
                    <span class="text-soft-silk font-medium">Generated Images</span>
                </template>
            </div>

            <!-- Search -->
            <div class="flex min-w-0 flex-1 items-center justify-end gap-2">
                <button
                    v-if="isUserUploadsTab"
                    class="bg-stone-gray/10 hover:bg-stone-gray/20 text-soft-silk flex h-9 shrink-0
                        items-center gap-1.5 rounded-lg px-3 text-xs font-medium whitespace-nowrap
                        transition-colors"
                    :class="searchScope === 'all_uploads' ? 'text-ember-glow ring-ember-glow/30 ring-1' : ''"
                    :title="
                        searchScope === 'all_uploads'
                            ? 'Searching all upload folders'
                            : 'Searching the current folder only'
                    "
                    @click="
                        emit(
                            'update:searchScope',
                            searchScope === 'all_uploads' ? 'current' : 'all_uploads',
                        )
                    "
                >
                    <UiIcon
                        v-if="isAllUploadsLoading"
                        name="MaterialSymbolsProgressActivity"
                        class="h-3.5 w-3.5 animate-spin"
                    />
                    <UiIcon v-else name="MdiMagnify" class="h-3.5 w-3.5" />
                    <span>{{ searchScope === 'all_uploads' ? 'All uploads' : 'Current' }}</span>
                </button>
                <div class="relative min-w-0 flex-1 max-w-xs">
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
                            isUserUploadsTab
                                ? searchScope === 'all_uploads'
                                    ? 'Search all uploads...'
                                    : 'Search current folder...'
                                : isGoogleDriveTab
                                  ? 'Search Google Drive...'
                                  : 'Search generated images...'
                        "
                        class="bg-obsidian/60 border-stone-gray/20 text-soft-silk focus:border-ember-glow/50
                            h-9 w-full rounded-lg border py-2 pr-8 pl-9 text-sm transition-colors
                            focus:outline-none"
                        @input="emit('update:searchQuery', ($event.target as HTMLInputElement).value)"
                    />
                    <button
                        v-if="searchQuery"
                        class="text-stone-gray/60 hover:text-soft-silk absolute top-1/2 right-2 flex
                            h-6 w-6 -translate-y-1/2 items-center justify-center rounded-md
                            transition-colors"
                        @click="emit('update:searchQuery', '')"
                    >
                        <UiIcon name="MaterialSymbolsClose" class="h-4 w-4" />
                    </button>
                </div>
            </div>
        </div>

        <!-- Row 2: View + Sort + Filter | Bulk Actions + Upload -->
        <div class="flex flex-wrap items-center justify-between gap-2">
            <!-- Left: View + Sort + Filter -->
            <div class="flex flex-wrap items-center gap-2">
                <!-- View Mode Toggles -->
                <div class="bg-stone-gray/10 flex items-center rounded-lg p-0.5">
                    <button
                        v-for="mode in ['gallery', 'grid', 'list'] as const"
                        :key="mode"
                        class="flex h-7 w-7 items-center justify-center rounded transition-all"
                        :class="
                            viewMode === mode
                                ? 'bg-stone-gray/30 text-soft-silk'
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

                <!-- Sort Dropdown -->
                <div ref="sortMenuRef" class="relative">
                    <button
                        class="bg-stone-gray/10 hover:bg-stone-gray/20 text-stone-gray/80 flex h-8
                            items-center gap-1.5 rounded-lg px-2.5 text-xs font-medium transition-colors"
                        @click="toggleSortMenu"
                    >
                        <UiIcon name="MdiFilter" class="h-3.5 w-3.5" />
                        <span>{{ currentSortLabel }}</span>
                        <UiIcon
                            name="MdiArrowUp"
                            class="h-3 w-3 transition-transform"
                            :class="{ 'rotate-180': sortDirection === 'desc' }"
                        />
                    </button>
                    <!-- Sort dropdown panel -->
                    <Transition
                        enter-active-class="transition duration-150 ease-out"
                        enter-from-class="opacity-0 -translate-y-1 scale-95"
                        enter-to-class="opacity-100 translate-y-0 scale-100"
                        leave-active-class="transition duration-100 ease-in"
                        leave-from-class="opacity-100 translate-y-0 scale-100"
                        leave-to-class="opacity-0 -translate-y-1 scale-95"
                    >
                        <div
                            v-if="isSortMenuOpen"
                            class="bg-obsidian/95 border-stone-gray/20 text-soft-silk absolute top-full left-0
                                z-100 mt-1 flex min-w-44 flex-col rounded-xl border py-1 shadow-2xl
                                backdrop-blur-md"
                            @contextmenu.prevent
                        >
                            <p class="text-stone-gray/50 px-3 py-1 text-[10px] font-medium uppercase tracking-wide">
                                Sort by
                            </p>
                            <button
                                v-for="opt in sortOptions"
                                :key="opt.value"
                                class="hover:bg-stone-gray/10 flex w-full items-center gap-2 px-3 py-1.5
                                    text-left text-sm transition-colors"
                                @click="selectSort(opt.value)"
                            >
                                <UiIcon
                                    v-if="sortBy === opt.value"
                                    name="MaterialSymbolsCheckSmallRounded"
                                    class="text-ember-glow h-4 w-4 shrink-0"
                                />
                                <div v-else class="h-4 w-4 shrink-0" />
                                <span>{{ opt.label }}</span>
                            </button>
                            <div class="bg-stone-gray/15 mx-2 my-1 h-px" />
                            <button
                                class="hover:bg-stone-gray/10 flex w-full items-center gap-2 px-3 py-1.5 text-left
                                    text-sm transition-colors"
                                @click="emit('update:sortDirection', sortDirection === 'asc' ? 'desc' : 'asc')"
                            >
                                <UiIcon name="MdiArrowUp" class="h-4 w-4 shrink-0 transition-transform" :class="{ 'rotate-180': sortDirection === 'desc' }" />
                                <span>{{ sortDirection === 'asc' ? 'Ascending' : 'Descending' }}</span>
                            </button>
                        </div>
                    </Transition>
                </div>

                <!-- Filter -->
                <div class="flex shrink-0 items-center gap-2 text-sm">
                    <select
                        :value="fileTypeFilter"
                        class="bg-stone-gray/10 border-stone-gray/20 text-stone-gray/80 focus:border-ember-glow/50
                            h-8 rounded-lg border px-2 text-xs outline-none transition-colors"
                        @change="
                            emit(
                                'update:fileTypeFilter',
                                ($event.target as HTMLSelectElement).value as FileTypeFilter,
                            )
                        "
                    >
                        <option
                            v-for="option in fileTypeOptions"
                            :key="option.value"
                            :value="option.value"
                        >
                            {{ option.label }}
                        </option>
                    </select>
                    <button
                        class="rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors"
                        :class="
                            foldersFirst
                                ? 'text-ember-glow bg-ember-glow/10 ring-ember-glow/30 ring-1'
                                : 'text-stone-gray/60 bg-stone-gray/10 hover:bg-stone-gray/20'
                        "
                        title="Keep folders grouped before files"
                        @click="emit('update:foldersFirst', !foldersFirst)"
                    >
                        Folders first
                    </button>
                </div>
            </div>

            <!-- Right: Bulk Actions + Upload -->
            <div class="flex items-center gap-2">
                <!-- Bulk Actions -->
                <Transition name="bulk-actions">
                    <div
                        v-if="selectedCount > 0"
                        class="bg-stone-gray/10 flex shrink-0 items-center gap-0.5 rounded-lg p-1"
                    >
                        <span class="text-soft-silk px-1.5 text-xs font-semibold">{{ selectedCount }}</span>
                        <div class="bg-stone-gray/20 mx-0.5 h-4 w-px" />
                        <button
                            class="hover:bg-stone-gray/20 text-stone-gray/70 hover:text-soft-silk flex h-7 w-7
                                items-center justify-center rounded-md transition-colors
                                disabled:cursor-not-allowed disabled:opacity-30"
                            :disabled="selectedDownloadCount === 0"
                            title="Download selected"
                            @click="emit('downloadSelected')"
                        >
                            <UiIcon name="UilDownloadAlt" class="h-4 w-4" />
                        </button>
                        <button
                            v-if="isUserUploadsTab"
                            class="hover:bg-stone-gray/20 text-stone-gray/70 hover:text-soft-silk flex h-7 w-7
                                items-center justify-center rounded-md transition-colors
                                disabled:cursor-not-allowed disabled:opacity-30"
                            :disabled="selectedMovableCount === 0"
                            title="Move selected"
                            @click="emit('moveSelected')"
                        >
                            <UiIcon name="MdiFolderMoveOutline" class="h-4 w-4" />
                        </button>
                        <button
                            v-if="isUserUploadsTab"
                            class="hover:bg-stone-gray/20 text-stone-gray/70 hover:text-soft-silk flex h-7 w-7
                                items-center justify-center rounded-md transition-colors
                                disabled:cursor-not-allowed disabled:opacity-30"
                            :disabled="selectedMovableCount === 0 || isStorageFull"
                            title="Copy selected"
                            @click="emit('copySelected')"
                        >
                            <UiIcon name="MaterialSymbolsContentCopyOutlineRounded" class="h-4 w-4" />
                        </button>
                        <button
                            v-if="isUserUploadsTab"
                            class="hover:bg-red-500/15 text-red-400 flex h-7 w-7 items-center justify-center
                                rounded-md transition-colors"
                            title="Delete selected (Del)"
                            @click="emit('deleteSelected')"
                        >
                            <UiIcon name="MaterialSymbolsDeleteRounded" class="h-4 w-4" />
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
                                class="bg-obsidian/60 border-stone-gray/20 text-soft-silk focus:border-ember-glow/50
                                    h-9 w-48 rounded-lg border px-3 text-sm transition-colors focus:outline-none"
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
                        :class="isCreatingFolder ? 'ring-ember-glow/40 text-ember-glow ring-1' : ''"
                        title="New Folder"
                        @click="emit('update:isCreatingFolder', !isCreatingFolder)"
                    >
                        <UiIcon name="MdiFolderPlusOutline" class="h-5 w-5" />
                    </button>

                    <button
                        class="bg-stone-gray/10 hover:bg-stone-gray/20 text-soft-silk flex h-9 w-9
                            shrink-0 items-center justify-center rounded-lg transition-colors
                            disabled:cursor-not-allowed disabled:opacity-40"
                        title="Upload Folder"
                        :disabled="isStorageFull"
                        @click="emit('triggerFolderUpload')"
                    >
                        <UiIcon name="MdiFolderUploadOutline" class="h-5 w-5" />
                    </button>

                    <button
                        class="bg-ember-glow/10 hover:bg-ember-glow/20 text-ember-glow flex h-9 w-9
                            shrink-0 items-center justify-center rounded-lg transition-colors
                            disabled:cursor-not-allowed disabled:opacity-40"
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
