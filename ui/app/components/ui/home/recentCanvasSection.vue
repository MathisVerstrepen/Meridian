<script lang="ts" setup>
import type { Graph, Folder, Workspace } from '@/types/graph';
import UiUtilsSearchBar from '~/components/ui/utils/searchBar.vue';

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
    workspaces: {
        type: Array as PropType<Workspace[]>,
        default: () => [],
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

// --- Composables ---
const {
    activeWorkspaceId,
    activeWorkspace,
    handleWheel: handleWorkspaceWheel,
    initActiveWorkspace,
} = useSidebarWorkspaces(
    toRef(props, 'workspaces'),
    toRef(props, 'graphs'),
    toRef(props, 'folders'),
);

// --- Local State ---
const searchQuery = ref('');
const searchScope = ref<'workspace' | 'global'>('workspace');
const currentFolderId = ref<string | null>(null);
const searchBarRef = ref<InstanceType<typeof UiUtilsSearchBar> | null>(null);
const scrollContainer = ref<HTMLElement | null>(null);
const isMac = ref(false);

// --- Computed ---
const currentFolder = computed(() => {
    if (!currentFolderId.value) return null;
    return props.folders.find((f) => f.id === currentFolderId.value);
});

/**
 * Determines what items to display in the grid.
 * 1. If Searching: Show all matching graphs (flat list) respecting scope.
 * 2. If Folder Open: Show graphs inside that folder (workspace bound).
 * 3. If Root: Show Pinned Graphs -> Folders -> Loose Graphs (workspace bound).
 */
const displayedItems = computed(() => {
    // 1. Search Mode
    if (searchQuery.value) {
        const query = searchQuery.value.toLowerCase();
        let sourceGraphs = props.graphs;

        // Apply Scope Filtering
        if (searchScope.value === 'workspace' && activeWorkspaceId.value) {
            sourceGraphs = sourceGraphs.filter((g) => g.workspace_id === activeWorkspaceId.value);
        }

        const matches = sourceGraphs
            .filter((g) => g.name.toLowerCase().includes(query))
            .sort((a, b) => Number(b.pinned) - Number(a.pinned)); // Pinned first

        return matches.map((g) => ({ type: 'graph', data: g }));
    }

    // If no workspace selected yet (and not global searching), return empty
    if (!activeWorkspaceId.value) return [];

    // Pre-filter by workspace for standard view
    const workspaceGraphs = props.graphs.filter((g) => g.workspace_id === activeWorkspaceId.value);
    const workspaceFolders = props.folders.filter(
        (f) => f.workspace_id === activeWorkspaceId.value,
    );

    // 2. Folder View
    if (currentFolderId.value) {
        // Ensure folder belongs to current workspace
        const folder = workspaceFolders.find((f) => f.id === currentFolderId.value);
        if (!folder) return [];

        const folderGraphs = workspaceGraphs
            .filter((g) => g.folder_id === currentFolderId.value)
            .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());

        return folderGraphs.map((g) => ({ type: 'graph', data: g }));
    }

    // 3. Root View
    const pinned = workspaceGraphs.filter((g) => g.pinned).map((g) => ({ type: 'graph', data: g }));

    // Folders need to know how many items they contain for the UI
    const folderItems = workspaceFolders
        .map((f) => {
            const count = workspaceGraphs.filter((g) => g.folder_id === f.id).length;
            return { type: 'folder', data: f, count };
        })
        .sort((a, b) => a.data.name.localeCompare(b.data.name));

    const loose = workspaceGraphs
        .filter((g) => !g.pinned && !g.folder_id)
        .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
        .map((g) => ({ type: 'graph', data: g }));

    return [...pinned, ...folderItems, ...loose];
});

// --- Methods ---
const handleKeyDown = (event: KeyboardEvent) => {
    if ((event.key === 'k' || event.key === 'K') && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        searchBarRef.value?.focus();
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

// --- Watchers ---
watch(
    () => props.workspaces,
    () => {
        initActiveWorkspace();
    },
    { immediate: true, deep: true },
);

// Reset folder view when workspace changes
watch(activeWorkspaceId, () => {
    currentFolderId.value = null;
    searchQuery.value = '';
});

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
    handleWorkspaceWheel,
});
</script>

<template>
    <div class="flex h-full w-full flex-col items-center">
        <!-- Header Section -->
        <div class="relative mb-8 flex w-full items-center justify-center">
            <!-- Workspace Pagination & Name (Top Left) - Only in Root View -->
            <div
                v-if="!currentFolderId && workspaces.length > 1"
                class="absolute left-0 flex flex-col items-start gap-1.5"
            >
                <!-- Pagination Dots -->
                <div class="flex items-center gap-1.5">
                    <button
                        v-for="ws in workspaces"
                        :key="ws.id"
                        class="group relative flex h-4 w-4 shrink-0 items-center justify-center
                            focus-visible:outline-none"
                        :title="ws.name"
                        @click="activeWorkspaceId = ws.id"
                    >
                        <div
                            class="transition-all duration-300 ease-in-out"
                            :class="[
                                ws.id === activeWorkspaceId
                                    ? 'bg-ember-glow h-2.5 w-2.5 rounded-full'
                                    : `bg-stone-gray/30 group-hover:bg-stone-gray/60 h-2 w-2
                                        rounded-full`,
                            ]"
                        />
                    </button>
                </div>
                <!-- Workspace Name -->
                <span class="text-stone-gray/50 pl-0.5 text-xs font-bold tracking-wider uppercase">
                    {{ activeWorkspace?.name }}
                </span>
            </div>

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
                <UiUtilsSearchBar
                    ref="searchBarRef"
                    v-model:search-query="searchQuery"
                    v-model:search-scope="searchScope"
                    :is-mac="isMac"
                    placeholder="Search canvas..."
                />
            </div>
        </div>

        <!-- Grid Content -->
        <div
            v-if="!isLoading && displayedItems.length > 0"
            ref="scrollContainer"
            class="custom_scroll stable-scrollbar-gutter grid h-full w-full auto-rows-[9rem]
                grid-cols-4 gap-5 overflow-y-auto pb-8"
        >
            <template v-for="item in displayedItems" :key="item.data.id">
                <!-- FOLDER CARD -->
                <div
                    v-if="item.type === 'folder'"
                    class="bg-anthracite/30 hover:bg-anthracite/50 border-stone-gray/5 group
                        relative h-36 w-full cursor-pointer overflow-hidden rounded-2xl border-2
                        transition-all duration-200 ease-in-out"
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
                    <div
                        class="relative z-10 flex h-full w-full flex-col items-start justify-center
                            gap-5 p-6"
                    >
                        <div class="text-stone-gray flex items-center gap-3">
                            <UiIcon name="MdiFolderOutline" class="h-8 w-8 shrink-0" />
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
                        ? searchScope === 'workspace'
                            ? 'No matching canvas found in this workspace.'
                            : 'No matching canvas found.'
                        : currentFolderId
                          ? 'This folder is empty.'
                          : 'No recent canvas found in this workspace.'
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
