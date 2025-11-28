<script lang="ts" setup>
import type { Graph, Folder } from '@/types/graph';

// --- Props ---
const props = defineProps({
    graphs: {
        type: Array as PropType<Graph[]>,
        required: true,
    },
    folders: {
        type: Array as PropType<Folder[]>,
        required: true,
    },
    isLoading: {
        type: Boolean,
        default: false,
    },
});

// --- Emits ---
const emit = defineEmits<{
    (e: 'delete', id: string, name: string): void;
}>();

// --- Local State ---
const searchQuery = ref('');
const currentFolderId = ref<string | null>(null);
const searchInputRef = ref<HTMLInputElement | null>(null);
const scrollContainer = ref<HTMLElement | null>(null);
const isMac = ref(false);

// --- Computed ---
const currentFolder = computed(() => {
    if (!currentFolderId.value) return null;
    return props.folders.find((f) => f.id === currentFolderId.value);
});

/**
 * Determines what items to display in the grid.
 * 1. If Searching: Show all matching graphs (flat list).
 * 2. If Folder Open: Show graphs inside that folder.
 * 3. If Root: Show Pinned Graphs -> Folders -> Loose Graphs.
 */
const displayedItems = computed(() => {
    // 1. Search Mode (Global)
    if (searchQuery.value) {
        const query = searchQuery.value.toLowerCase();
        const matches = props.graphs
            .filter((g) => g.name.toLowerCase().includes(query))
            .sort((a, b) => Number(b.pinned) - Number(a.pinned)); // Pinned first

        return matches.map((g) => ({ type: 'graph', data: g }));
    }

    // 2. Folder View
    if (currentFolderId.value) {
        const folderGraphs = props.graphs
            .filter((g) => g.folder_id === currentFolderId.value)
            .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());

        return folderGraphs.map((g) => ({ type: 'graph', data: g }));
    }

    // 3. Root View
    const pinned = props.graphs.filter((g) => g.pinned).map((g) => ({ type: 'graph', data: g }));

    // Folders need to know how many items they contain for the UI
    const folderItems = props.folders
        .map((f) => {
            const count = props.graphs.filter((g) => g.folder_id === f.id).length;
            return { type: 'folder', data: f, count };
        })
        .sort((a, b) => a.data.name.localeCompare(b.data.name));

    const loose = props.graphs
        .filter((g) => !g.pinned && !g.folder_id)
        .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
        .map((g) => ({ type: 'graph', data: g }));

    return [...pinned, ...folderItems, ...loose];
});

// --- Methods ---
const handleShiftSpace = () => {
    document.execCommand('insertText', false, ' ');
};

const handleKeyDown = (event: KeyboardEvent) => {
    if ((event.key === 'k' || event.key === 'K') && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        searchInputRef.value?.focus();
    }
};

const openFolder = (folderId: string) => {
    currentFolderId.value = folderId;
    searchQuery.value = ''; // Clear search when entering folder
};

const goBack = () => {
    currentFolderId.value = null;
    searchQuery.value = '';
};

// --- Lifecycle ---
onMounted(() => {
    isMac.value = /Mac|iPhone|iPad|iPod/.test(navigator.userAgent);
    document.addEventListener('keydown', handleKeyDown);
});

onBeforeUnmount(() => {
    document.removeEventListener('keydown', handleKeyDown);
});

// --- Expose ---
// Expose the scroll container so the parent (index.vue) can attach the scroll animation listener
defineExpose({
    scrollContainer,
});
</script>

<template>
    <div class="flex h-full w-full flex-col items-center">
        <!-- Header Section -->
        <div class="relative mb-8 flex w-full items-center justify-center">
            <!-- Back Button (only in folder view) -->
            <button
                v-if="currentFolderId"
                class="text-stone-gray hover:bg-stone-gray/10 absolute left-0 flex items-center
                    gap-2 rounded-lg px-3 py-1.5 text-sm font-bold transition-colors"
                @click="goBack"
            >
                <UiIcon name="MdiArrowUp" class="h-5 w-5 -rotate-90" />
                Back
            </button>

            <!-- Title -->
            <h2 class="font-outfit text-stone-gray text-xl font-bold">
                <span v-if="currentFolderId && currentFolder">
                    <UiIcon name="MdiFolderOutline" class="mb-1 inline h-5 w-5 opacity-70" />
                    {{ currentFolder.name }}
                </span>
                <span v-else>Recent Canvas</span>
            </h2>

            <!-- Search Input -->
            <div v-if="!isLoading && graphs.length > 0" class="absolute right-0 w-72">
                <UiIcon
                    name="MdiMagnify"
                    class="text-stone-gray/50 pointer-events-none absolute top-1/2 left-3 h-5 w-5
                        -translate-y-1/2"
                />
                <input
                    ref="searchInputRef"
                    v-model="searchQuery"
                    type="text"
                    placeholder="Search canvas..."
                    class="dark:bg-stone-gray/25 bg-obsidian/50 placeholder:text-stone-gray/50
                        text-stone-gray block h-9 w-full rounded-xl border-transparent px-3 py-2
                        pr-16 pl-10 text-sm font-semibold focus:border-transparent focus:ring-0
                        focus:outline-none"
                    @keydown.space.shift.exact.prevent="handleShiftSpace"
                />
                <div
                    class="text-stone-gray/30 absolute top-1/2 right-3 ml-auto -translate-y-1/2
                        rounded-md border px-1 py-0.5 text-[10px] font-bold"
                >
                    {{ isMac ? '⌘ + K' : 'CTRL + K' }}
                </div>
            </div>
        </div>

        <!-- Grid Content -->
        <div
            v-if="!isLoading && displayedItems.length > 0"
            ref="scrollContainer"
            class="custom_scroll grid h-full w-full auto-rows-[9rem] grid-cols-4 gap-5
                overflow-y-auto pb-8"
        >
            <template v-for="item in displayedItems" :key="item.data.id">
                <!-- FOLDER CARD -->
                <div
                    v-if="item.type === 'folder'"
                    class="bg-anthracite/30 hover:bg-anthracite/50 border-stone-gray/5 group
                        relative flex h-36 w-full cursor-pointer flex-col items-start justify-center
                        gap-5 overflow-hidden rounded-2xl border-2 p-6 transition-all duration-200
                        ease-in-out"
                    :style="
                        (item.data as Folder).color
                            ? ({
                                  borderColor: (item.data as Folder).color,
                                  '--folder-color': (item.data as Folder).color,
                              } as any)
                            : {}
                    "
                    :class="{
                        'folder-card-colored': (item.data as Folder).color,
                    }"
                    role="button"
                    @click="openFolder((item.data as Folder).id)"
                >
                    <div class="text-stone-gray flex items-center gap-3">
                        <UiIcon name="MdiFolderOutline" class="text-ember-glow h-8 w-8 shrink-0" />
                        <span class="line-clamp-2 text-lg font-bold">
                            {{ (item.data as Folder).name }}
                        </span>
                    </div>
                    <div class="flex w-full items-center justify-between text-sm">
                        <div
                            class="bg-stone-gray/10 text-stone-gray/70 rounded-lg px-3 py-1
                                font-bold"
                        >
                            {{ (item as any).count }} items
                        </div>
                    </div>
                </div>

                <!-- GRAPH CARD -->
                <NuxtLink
                    v-else
                    class="bg-anthracite/50 hover:bg-anthracite/75 border-stone-gray/10 group
                        relative flex h-36 w-full cursor-pointer flex-col items-start justify-center
                        gap-5 overflow-hidden rounded-2xl border-2 p-6 transition-colors
                        duration-200 ease-in-out"
                    role="button"
                    :to="{ name: 'graph-id', params: { id: item.data.id } }"
                >
                    <button
                        class="hover:bg-terracotta-clay/10 text-terracotta-clay absolute top-2
                            right-2 flex items-center rounded-md p-2 text-sm font-bold opacity-0
                            transition-all duration-200 ease-in-out group-hover:opacity-100"
                        @click.prevent="emit('delete', item.data.id, item.data.name)"
                    >
                        <UiIcon
                            name="MaterialSymbolsDeleteRounded"
                            class="text-terracotta-clay h-4 w-4"
                            aria-hidden="true"
                        />
                    </button>

                    <div class="text-stone-gray flex items-center gap-3">
                        <UiIcon
                            v-if="(item.data as Graph).pinned"
                            name="MajesticonsPin"
                            class="h-6 w-6 shrink-0"
                        />
                        <UiIcon
                            v-else
                            name="MaterialSymbolsFlowchartSharp"
                            class="h-7 w-7 shrink-0"
                        />

                        <span class="line-clamp-2 text-lg font-bold">
                            {{ (item.data as Graph).name }}
                        </span>
                    </div>

                    <div class="flex w-full items-center justify-between text-sm">
                        <div
                            class="bg-ember-glow/5 text-ember-glow/70 rounded-lg px-3 py-1
                                font-bold"
                        >
                            {{ (item.data as Graph).node_count }} nodes
                        </div>

                        <NuxtTime
                            class="text-stone-gray"
                            :datetime="new Date((item.data as Graph).updated_at)"
                            locale="en-US"
                            relative
                        />
                    </div>
                </NuxtLink>
            </template>
        </div>

        <!-- Empty State -->
        <div
            v-if="!isLoading && displayedItems.length === 0"
            class="flex h-full w-full items-center justify-center"
        >
            <span class="text-soft-silk/50">
                {{
                    searchQuery
                        ? 'No matching canvas found.'
                        : currentFolderId
                          ? 'This folder is empty.'
                          : 'No recent canvas found. Create a new one!'
                }}
            </span>
        </div>

        <!-- Loading State -->
        <div
            v-if="isLoading"
            class="flex h-full w-full flex-col items-center justify-center gap-4 opacity-50"
        >
            <div
                class="border-soft-silk h-8 w-8 animate-spin rounded-full border-4
                    border-t-transparent"
            />
            <span class="text-soft-silk">Loading canvas...</span>
            <!-- Fade Overlay -->
            <div
                class="from-anthracite/20 pointer-events-none absolute bottom-0 left-0 h-16 w-full
                    bg-gradient-to-t to-transparent"
            />
        </div>
    </div>
</template>

<style scoped>
.folder-card-colored {
    position: relative;
}

.folder-card-colored::before,
.folder-card-colored::after {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: inherit;
    pointer-events: none;
    transition: opacity 0.2s ease-in-out;
}

.folder-card-colored::before {
    background: linear-gradient(to right, var(--folder-color), rgba(38, 38, 38, 0.3) 20%);
    opacity: 1;
}

.folder-card-colored::after {
    background: linear-gradient(to right, var(--folder-color), rgba(38, 38, 38, 0.5) 40%);
    opacity: 0;
}

.folder-card-colored:hover::before {
    opacity: 0;
}

.folder-card-colored:hover::after {
    opacity: 1;
}
</style>
