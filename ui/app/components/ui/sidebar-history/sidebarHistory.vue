<script lang="ts" setup>
import { useResizeObserver, useMutationObserver } from '@vueuse/core';
import UiSidebarHistorySearch from './sidebarHistorySearch.vue';

// --- Stores ---
const sidebarCanvasStore = useSidebarCanvasStore();
const { isLeftOpen } = storeToRefs(sidebarCanvasStore);
const { toggleLeftSidebar } = sidebarCanvasStore;
const { updateGraphName } = useAPI();

// --- Composables ---
const {
    graphs,
    folders,
    workspaces,
    searchQuery,
    searchResults,
    expandedFolders,
    fetchData,
    toggleFolder,
    getOrganizedData,
    initExpandedFolders,
} = useSidebarData();

const {
    activeWorkspaceId,
    activeWorkspace,
    isEditingWorkspace,
    workspaceNameInput,
    workspaceInputRef,
    initActiveWorkspace,
    handleCreateWorkspace,
    startEditingWorkspace,
    saveWorkspaceName,
    cancelWorkspaceEdit,
    handleDeleteWorkspace,
    handleWheel,
} = useSidebarWorkspaces(workspaces, graphs);

const {
    editingId,
    editInputValue,
    createGraphHandler,
    createTemporaryGraphHandler,
    createFolderHandler,
    handleStartRename,
    confirmRename,
    cancelRename,
    handleMoveGraph,
    handleDeleteFolder,
    handleUpdateFolderColor,
    handlePin,
    handleRegenerateTitle,
    handleImportGraph,
    setInputRef,
    navigateToGraph,
    exportGraph,
} = useSidebarActions(graphs, folders, activeWorkspace, expandedFolders, fetchData);

const route = useRoute();
const graphEvents = useGraphEvents();

// --- Local Utils ---
const historyListRef = ref<HTMLDivElement | null>(null) as Ref<HTMLDivElement | null>;
const searchComponentRef = ref<InstanceType<typeof UiSidebarHistorySearch> | null>(null);
const isOverflowing = ref(false);
const isMac = ref(false);
const isTemporaryOpen = computed(() => route.query.temporary === 'true');
const currentGraphId = computed(() => route.params.id as string | undefined);

// Use existing graph deletion composable
const { handleDeleteGraph } = useGraphDeletion(graphs, currentGraphId);

const organizedData = computed(() => getOrganizedData(activeWorkspaceId.value));

// --- Resize Logic ---
const checkOverflow = () => {
    if (historyListRef.value) {
        const { scrollHeight, clientHeight } = historyListRef.value;
        isOverflowing.value = scrollHeight > clientHeight + 1;
    }
};

useResizeObserver(historyListRef, checkOverflow);
useMutationObserver(historyListRef, checkOverflow, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ['style', 'class'],
});

// --- Key Bindings ---
const handleKeyDown = (event: KeyboardEvent) => {
    if (
        ((event.key === 'N' || event.key === 'n') && event.altKey) ||
        ((event.key === 'N' || event.key === 'n') && event.metaKey)
    ) {
        event.preventDefault();
        createGraphHandler();
    }

    if ((event.key === 'k' || event.key === 'K') && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        searchComponentRef.value?.focus();
    }
};

// --- Watchers ---
watch(
    [graphs, currentGraphId],
    ([newGraphs, newGraphId]) => {
        if (newGraphs.length > 0 && newGraphId) {
            const currentGraph = newGraphs.find((g) => g.id === newGraphId);
            if (currentGraph && currentGraph.folder_id) {
                expandedFolders.value.add(currentGraph.folder_id);
            }
        }
    },
    { deep: true },
);

// --- Lifecycle ---
onMounted(async () => {
    isMac.value = /Mac|iPhone|iPad|iPod/.test(navigator.userAgent);
    initExpandedFolders();

    const unsubscribeUpdateName = graphEvents.on('update-name', async ({ graphId, name }) => {
        const graphToUpdate = graphs.value.find((g) => g.id === graphId);
        if (graphToUpdate) {
            graphToUpdate.name = name;
            await updateGraphName(graphId, name);
        }
    });
    const unsubscribeGraphPersisted = graphEvents.on('graph-persisted', fetchData);

    onUnmounted(() => {
        unsubscribeUpdateName();
        unsubscribeGraphPersisted();
        document.removeEventListener('keydown', handleKeyDown);
    });

    await fetchData();
    initActiveWorkspace();
    document.addEventListener('keydown', handleKeyDown);
});
</script>

<template>
    <div
        id="sidebar-history"
        class="dark:bg-anthracite/75 bg-stone-gray/20 border-stone-gray/10 absolute top-2 left-2
            z-10 flex h-[calc(100%-1rem)] flex-col overflow-hidden rounded-2xl border-2 px-4 pt-10
            pb-4 shadow-lg backdrop-blur-md transition-[width] duration-200 ease-in-out"
        :class="{
            'pointer-events-auto w-[25rem]': isLeftOpen,
            'pointer-events-none w-[3rem]': !isLeftOpen,
        }"
        @wheel="handleWheel"
    >
        <UiSidebarHistoryLogo class="hide-close" />

        <UiSidebarHistoryHeader
            :is-mac="isMac"
            :is-temporary-open="isTemporaryOpen"
            @create-graph="createGraphHandler"
            @create-folder="createFolderHandler"
            @create-temporary-graph="createTemporaryGraphHandler"
        />

        <UiSidebarHistorySearch
            ref="searchComponentRef"
            v-model:search-query="searchQuery"
            :is-mac="isMac"
            @import="handleImportGraph"
        />

        <!-- Workspace Header -->
        <div v-if="activeWorkspace" class="hide-close mt-2 flex items-center justify-between px-1">
            <div class="flex flex-1 items-center">
                <div v-if="isEditingWorkspace" class="w-full max-w-[150px]">
                    <input
                        ref="workspaceInputRef"
                        v-model="workspaceNameInput"
                        type="text"
                        class="bg-anthracite/20 text-stone-gray w-full rounded px-1 text-sm
                            font-bold outline-none"
                        @blur="saveWorkspaceName"
                        @keydown.enter="saveWorkspaceName"
                        @keydown.esc="cancelWorkspaceEdit"
                    />
                </div>
                <h2
                    v-else
                    class="text-stone-gray/50 hover:text-stone-gray cursor-pointer truncate text-sm
                        font-bold transition-colors"
                    title="Rename Workspace"
                    @click="startEditingWorkspace"
                >
                    {{ activeWorkspace.name }}
                </h2>
            </div>

            <button
                v-if="workspaces.length > 1 && activeWorkspaceId !== workspaces[0].id"
                class="text-stone-gray/50 hover:text-stone-gray mr-2 hover:cursor-pointer"
                title="Delete workspace"
                @click="handleDeleteWorkspace()"
            >
                <UiIcon name="MaterialSymbolsDeleteRounded" class="h-3 w-3" />
            </button>

            <button
                class="text-stone-gray/50 hover:text-stone-gray hover:cursor-pointer"
                title="Create new workspace"
                @click="handleCreateWorkspace"
            >
                <UiIcon name="Fa6SolidPlus" class="h-3 w-3" />
            </button>
        </div>

        <div
            ref="historyListRef"
            class="hide-close hide-scrollbar relative mt-2 flex grow flex-col space-y-2
                overflow-y-auto pb-2"
        >
            <div
                v-if="graphs.length === 0 && folders.length === 0"
                class="text-stone-gray/50 mt-4 flex animate-pulse justify-center text-sm font-bold"
            >
                Loading history...
            </div>

            <template v-else-if="searchQuery">
                <div
                    v-if="searchResults.length === 0"
                    class="text-stone-gray/50 mt-4 flex justify-center text-sm font-bold"
                >
                    No matching canvas found.
                </div>
                <UiSidebarHistoryItem
                    v-for="graph in searchResults"
                    :key="graph.id"
                    :graph="graph"
                    :current-graph-id="currentGraphId"
                    :editing-id="editingId"
                    :edit-input-value="editInputValue"
                    :folders="folders"
                    :workspaces="workspaces"
                    @navigate="navigateToGraph"
                    @start-rename="(graphId, graphName) => handleStartRename(graphId, graphName)"
                    @update:edit-input-value="(val) => (editInputValue = val)"
                    @confirm-rename="confirmRename"
                    @cancel-rename="cancelRename"
                    @set-input-ref="setInputRef"
                    @delete="(graphId, graphName) => handleDeleteGraph(graphId, graphName, true)"
                    @download="exportGraph"
                    @pin="handlePin"
                    @move="handleMoveGraph"
                    @regenerate-title="handleRegenerateTitle"
                />
            </template>

            <template v-else-if="organizedData">
                <!-- PINNED CANVAS -->
                <div v-if="organizedData.pinned.length > 0" class="space-y-2">
                    <UiSidebarHistoryItem
                        v-for="graph in organizedData.pinned"
                        :key="graph.id"
                        :graph="graph"
                        :current-graph-id="currentGraphId"
                        :editing-id="editingId"
                        :edit-input-value="editInputValue"
                        :folders="folders"
                        :workspaces="workspaces"
                        @navigate="navigateToGraph"
                        @start-rename="
                            (graphId, graphName) => handleStartRename(graphId, graphName)
                        "
                        @update:edit-input-value="(val) => (editInputValue = val)"
                        @confirm-rename="confirmRename"
                        @cancel-rename="cancelRename"
                        @set-input-ref="setInputRef"
                        @delete="
                            (graphId, graphName) => handleDeleteGraph(graphId, graphName, true)
                        "
                        @download="exportGraph"
                        @pin="handlePin"
                        @move="handleMoveGraph"
                        @regenerate-title="handleRegenerateTitle"
                    />
                </div>

                <!-- FOLDERS CANVAS -->
                <UiSidebarHistoryFolder
                    v-for="folder in organizedData.folders"
                    :key="folder.id"
                    :folder="folder"
                    :is-expanded="expandedFolders.has(folder.id)"
                    :editing-id="editingId"
                    :edit-input-value="editInputValue"
                    :current-graph-id="currentGraphId"
                    :all-folders="folders"
                    :workspaces="workspaces"
                    @toggle="toggleFolder"
                    @start-rename="handleStartRename"
                    @delete="handleDeleteFolder"
                    @update:edit-input-value="(val) => (editInputValue = val)"
                    @confirm-rename="confirmRename"
                    @cancel-rename="cancelRename"
                    @set-input-ref="setInputRef"
                    @navigate="navigateToGraph"
                    @start-graph-rename="handleStartRename"
                    @delete-graph="
                        (graphId, graphName) => handleDeleteGraph(graphId, graphName, true)
                    "
                    @download-graph="exportGraph"
                    @pin-graph="handlePin"
                    @move-graph="handleMoveGraph"
                    @update-folder-color="handleUpdateFolderColor"
                    @regenerate-title="handleRegenerateTitle"
                />

                <!-- LOOSE CANVAS -->
                <div class="space-y-2">
                    <UiSidebarHistoryItem
                        v-for="graph in organizedData.loose"
                        :key="graph.id"
                        :graph="graph"
                        :current-graph-id="currentGraphId"
                        :editing-id="editingId"
                        :edit-input-value="editInputValue"
                        :folders="folders"
                        :workspaces="workspaces"
                        @navigate="navigateToGraph"
                        @start-rename="
                            (graphId, graphName) => handleStartRename(graphId, graphName)
                        "
                        @update:edit-input-value="(val) => (editInputValue = val)"
                        @confirm-rename="confirmRename"
                        @cancel-rename="cancelRename"
                        @set-input-ref="setInputRef"
                        @delete="
                            (graphId, graphName) => handleDeleteGraph(graphId, graphName, true)
                        "
                        @download="exportGraph"
                        @pin="handlePin"
                        @move="handleMoveGraph"
                        @regenerate-title="handleRegenerateTitle"
                    />
                </div>
            </template>
        </div>

        <div
            v-show="isOverflowing"
            class="hide-close pointer-events-none absolute bottom-[80px] left-0 h-12 w-full px-4"
        >
            <div
                class="dark:from-anthracite/75 from-stone-gray/20 absolute z-10 h-12 w-[364px]
                    bg-gradient-to-t to-transparent"
            />
            <div class="from-obsidian absolute h-12 w-[364px] bg-gradient-to-t to-transparent" />
        </div>

        <!-- Pagination -->
        <UiSidebarHistoryWorkspacePagination
            class="hide-close"
            :workspaces="workspaces"
            :active-id="activeWorkspaceId"
            @select="(id) => (activeWorkspaceId = id)"
        />

        <UiSidebarHistoryUserProfileCard class="hide-close" />
        <div
            class="bg-anthracite hover:bg-obsidian/20 border-stone-gray/10 pointer-events-auto
                absolute top-10 right-2.5 flex h-10 w-6 cursor-pointer items-center justify-center
                rounded-lg border-2 transition duration-200 ease-in-out"
            role="button"
            @click="toggleLeftSidebar"
        >
            <UiIcon
                name="TablerChevronCompactLeft"
                class="text-stone-gray h-6 w-6"
                :class="{ 'rotate-180': !isLeftOpen, 'rotate-0': isLeftOpen }"
            />
        </div>
    </div>
</template>

<style scoped>
#sidebar-history:not(.w-\[25rem\]) .hide-close {
    opacity: 0;
    transition: opacity 0.2s ease-in-out;
}
</style>
