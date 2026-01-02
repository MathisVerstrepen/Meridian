<script lang="ts" setup>
import { AnimatePresence, motion } from 'motion-v';

defineProps<{
    breadcrumbs: FileSystemObject[];
    searchQuery: string;
    viewMode: ViewMode;
    sortBy: SortOption;
    sortDirection: SortDirection;
    isUserUploadsTab: boolean;
    isCreatingFolder: boolean;
    newFolderName: string;
    isStorageFull: boolean;
}>();

const emit = defineEmits<{
    (e: 'navigate', folder: FileSystemObject): void;
    (e: 'update:searchQuery', query: string): void;
    (e: 'toggleViewMode', mode: ViewMode): void;
    (e: 'update:sortBy', sort: SortOption): void;
    (e: 'update:sortDirection', dir: SortDirection): void;
    (e: 'update:isCreatingFolder', val: boolean): void;
    (e: 'update:newFolderName', val: string): void;
    (e: 'createFolder'): void;
    (e: 'triggerUpload'): void;
    (e: 'triggerFolderUpload'): void;
}>();
</script>

<template>
    <div class="flex items-center justify-between">
        <!-- Breadcrumbs -->
        <div class="flex min-h-[36px] items-center gap-1 text-sm">
            <template v-if="isUserUploadsTab">
                <button
                    class="bg-stone-gray/10 hover:bg-stone-gray/20 text-soft-silk mr-2 flex h-9 w-9
                        shrink-0 items-center justify-center rounded-lg transition-colors
                        duration-200 ease-in-out disabled:cursor-not-allowed disabled:opacity-50"
                    title="Go back"
                    :disabled="breadcrumbs.length <= 1"
                    @click="emit('navigate', breadcrumbs[breadcrumbs.length - 2])"
                >
                    <UiIcon name="LineMdChevronSmallUp" class="h-5 w-5 -rotate-90" />
                </button>
                <span
                    v-for="(part, index) in breadcrumbs"
                    :key="part.id"
                    class="text-stone-gray/60 flex items-center gap-1"
                >
                    <span v-if="index > 0" class="text-stone-gray/40">/</span>
                    <button
                        class="hover:text-soft-silk transition-colors"
                        :disabled="index === breadcrumbs.length - 1"
                        @click="emit('navigate', part)"
                    >
                        {{ part.name === '/' ? 'Root' : part.name }}
                    </button>
                </span>
            </template>
            <template v-else>
                <span class="text-soft-silk font-medium">Generated Images</span>
            </template>
        </div>

        <!-- Search & Controls -->
        <div class="flex items-center gap-2">
            <!-- Search -->
            <div class="relative w-full max-w-xs">
                <UiIcon
                    name="MdiMagnify"
                    class="text-stone-gray/60 pointer-events-none absolute top-1/2 left-3 h-4 w-4
                        -translate-y-1/2"
                />
                <input
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

            <div class="bg-stone-gray/20 mx-2 h-5 w-px" />

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

            <div class="bg-stone-gray/20 mx-2 h-5 w-px" />

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

            <!-- Upload Controls -->
            <template v-if="isUserUploadsTab">
                <div class="bg-stone-gray/20 mx-2 h-5 w-px" />

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
</template>
