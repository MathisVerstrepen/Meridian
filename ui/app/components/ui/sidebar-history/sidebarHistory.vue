<script lang="ts" setup>
import type { Graph, Folder, Workspace } from '@/types/graph';
import { useResizeObserver, useDebounceFn, useThrottleFn } from '@vueuse/core';
import UiSidebarHistorySearch from './sidebarHistorySearch.vue';
import { PLAN_LIMITS } from '@/constants/limits';
import type { User } from '@/types/user';

// --- Stores ---
const chatStore = useChatStore();
const globalSettingsStore = useSettingsStore();
const sidebarCanvasStore = useSidebarCanvasStore();
const streamStore = useStreamStore();

// --- State from Stores (Reactive Refs) ---
const { upcomingModelData, lastOpenedChatId, openChatId } = storeToRefs(chatStore);
const { modelsSettings } = storeToRefs(globalSettingsStore);
const { isLeftOpen } = storeToRefs(sidebarCanvasStore);

// --- Actions/Methods from Stores ---
const { resetChatState } = chatStore;
const { toggleLeftSidebar } = sidebarCanvasStore;
const { regenerateTitle } = streamStore;

// --- Routing ---
const route = useRoute();

// --- Composables ---
const {
    getGraphs,
    createGraph,
    updateGraphName,
    togglePin,
    exportGraph,
    importGraph,
    getHistoryFolders,
    createHistoryFolder,
    updateHistoryFolder,
    moveGraph,
    deleteHistoryFolder,
    getWorkspaces,
    createWorkspace,
    updateWorkspace,
    deleteWorkspace,
} = useAPI();

const { user } = useUserSession();
const graphEvents = useGraphEvents();
const { error, success } = useToast();

// --- Local State ---
const STORAGE_KEY = 'meridian_expanded_folders';
const WORKSPACE_STORAGE_KEY = 'meridian_active_workspace';

const graphs = ref<Graph[]>([]);
const folders = ref<Folder[]>([]);
const workspaces = ref<Workspace[]>([]);
const activeWorkspaceId = ref<string | null>(null);
const expandedFolders = ref<Set<string>>(new Set());
const searchQuery = ref('');

const editingId = ref<string | null>(null);
const editInputValue = ref<string>('');
const inputRefs = ref(new Map<string, HTMLInputElement>());

// Workspace editing state
const isEditingWorkspace = ref(false);
const workspaceNameInput = ref('');
const workspaceInputRef = ref<HTMLInputElement | null>(null);

const historyListRef: Ref<HTMLDivElement | null> = ref(null);
const searchComponentRef = ref<InstanceType<typeof UiSidebarHistorySearch> | null>(null);
const isOverflowing = ref(false);
const isMac = ref(false);
const isTemporaryOpen = computed(() => route.query.temporary === 'true');
const currentGraphId = computed(() => route.params.id as string | undefined);
const { handleDeleteGraph } = useGraphDeletion(graphs, currentGraphId);

const isLimitReached = computed(() => {
    if ((user.value as User)?.plan_type !== 'free') return false;
    const nonTemporaryGraphs = graphs.value.filter((g) => !g.temporary);
    return nonTemporaryGraphs.length >= PLAN_LIMITS.FREE.MAX_GRAPHS;
});

// --- Computed Properties ---
const activeWorkspace = computed(() =>
    workspaces.value.find((w) => w.id === activeWorkspaceId.value),
);

const searchResults = computed(() => {
    if (!searchQuery.value) return [];
    return graphs.value
        .filter((graph) => graph.name.toLowerCase().includes(searchQuery.value.toLowerCase()))
        .sort((a, b) => Number(b.pinned) - Number(a.pinned));
});

const organizedData = computed(() => {
    if (searchQuery.value) return null;
    if (!activeWorkspace.value) return null;

    const wsId = activeWorkspace.value.id;

    const wsFolders = folders.value.filter((f) => f.workspace_id === wsId);
    const wsGraphs = graphs.value.filter((g) => g.workspace_id === wsId);

    const pinned = wsGraphs.filter((g) => g.pinned);
    const unpinned = wsGraphs.filter((g) => !g.pinned);

    const folderMap = wsFolders
        .map((folder) => ({
            ...folder,
            graphs: graphs.value
                .filter((g) => g.folder_id === folder.id)
                .sort(
                    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
                ),
        }))
        .sort((a, b) => a.name.localeCompare(b.name));

    const loose = unpinned
        .filter((g) => !g.folder_id)
        .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());

    return {
        pinned,
        folders: folderMap,
        loose,
    };
});

// --- Core Logic Functions ---
const fetchData = async () => {
    try {
        const [graphsData, foldersData, workspacesData] = await Promise.all([
            getGraphs(),
            getHistoryFolders(),
            getWorkspaces(),
        ]);
        graphs.value = graphsData;
        folders.value = foldersData;
        workspaces.value = workspacesData;

        // Restore active workspace from localStorage or default to first available
        if (workspaces.value.length > 0) {
            const storedId = localStorage.getItem(WORKSPACE_STORAGE_KEY);
            const exists = workspaces.value.find((w) => w.id === storedId);

            if (exists) {
                activeWorkspaceId.value = exists.id;
            } else if (
                !activeWorkspaceId.value ||
                !workspaces.value.find((w) => w.id === activeWorkspaceId.value)
            ) {
                activeWorkspaceId.value = workspaces.value[0].id;
            }
        }
    } catch (err: unknown) {
        console.error('Error fetching data:', err);
        error('Failed to load history.', { title: 'Load Error' });
    }
};

const handleCreateWorkspace = async () => {
    try {
        const newWs = await createWorkspace('New Workspace');
        workspaces.value.push(newWs);
        activeWorkspaceId.value = newWs.id;
        startEditingWorkspace();
    } catch {
        error('Failed to create workspace.');
    }
};

const startEditingWorkspace = async () => {
    if (!activeWorkspace.value) return;
    workspaceNameInput.value = activeWorkspace.value.name;
    isEditingWorkspace.value = true;
    await nextTick();
    workspaceInputRef.value?.focus();
    workspaceInputRef.value?.select();
};

const saveWorkspaceName = async () => {
    if (!isEditingWorkspace.value || !activeWorkspace.value) return;
    const newName = workspaceNameInput.value.trim();
    if (newName && newName !== activeWorkspace.value.name) {
        try {
            const updated = await updateWorkspace(activeWorkspace.value.id, newName);
            activeWorkspace.value.name = updated.name;
        } catch {
            error('Failed to rename workspace.');
        }
    }
    isEditingWorkspace.value = false;
};

const cancelWorkspaceEdit = () => {
    isEditingWorkspace.value = false;
};

const createGraphHandler = async () => {
    if (isLimitReached.value) {
        error('You have reached the maximum number of canvases for the Free plan.', {
            title: 'Limit Reached',
        });
        return;
    }

    try {
        const wsId = activeWorkspace.value?.id;
        const newGraph = await createGraph(false, wsId);
        if (newGraph) {
            graphs.value.unshift(newGraph);
            upcomingModelData.value.data.model = modelsSettings.value.defaultModel;
            navigateToGraph(newGraph.id, false);
        }
    } catch (err: unknown) {
        console.error('Failed to create graph from component:', err);
        const detail =
            (err as { data?: { detail?: string } })?.data?.detail ||
            (err as { message?: string })?.message ||
            '';
        if (detail === 'FREE_TIER_CANVAS_LIMIT_REACHED') {
            error('You have reached the maximum number of canvases for the Free plan.', {
                title: 'Limit Reached',
            });
        } else {
            error('Failed to create new canvas. Please try again.', {
                title: 'Graph Creation Error',
            });
        }
    }
};

const createTemporaryGraphHandler = async () => {
    try {
        const wsId = activeWorkspace.value?.id;
        const newGraph = await createGraph(true, wsId);
        if (newGraph) {
            upcomingModelData.value.data.model = modelsSettings.value.defaultModel;
            navigateToGraph(newGraph.id, true);
        }
    } catch (err) {
        console.error('Failed to create temporary graph from component:', err);
        error('Failed to create new temporary canvas. Please try again.', {
            title: 'Temporary Graph Creation Error',
        });
    }
};

const createFolderHandler = async () => {
    try {
        const wsId = activeWorkspace.value?.id;
        const newFolder = await createHistoryFolder('New Folder', wsId);
        folders.value.push(newFolder);
        expandedFolders.value.add(newFolder.id);
        handleStartRename(newFolder.id, newFolder.name);
    } catch (err) {
        console.error('Failed to create folder from component:', err);
        error('Failed to create new folder. Please try again.', {
            title: 'Folder Creation Error',
        });
    }
};

const navigateToGraph = (id: string, temporary: boolean) => {
    if (id === editingId.value) return;
    resetChatState();
    lastOpenedChatId.value = null;
    openChatId.value = null;
    navigateTo(`/graph/${id}?temporary=${temporary}`);
};

const toggleFolder = (folderId: string) => {
    if (expandedFolders.value.has(folderId)) {
        expandedFolders.value.delete(folderId);
    } else {
        expandedFolders.value.add(folderId);
    }
};

const handleStartRename = async (id: string, currentName: string) => {
    editingId.value = id;
    editInputValue.value = currentName;
    await nextTick();
    const input = inputRefs.value.get(id);
    if (input) {
        input.focus();
        input.select();
    }
};

const confirmRename = async () => {
    if (!editingId.value) return;
    const id = editingId.value;
    const newName = editInputValue.value.trim();
    editingId.value = null;

    // Check if it's a folder
    const folderIndex = folders.value.findIndex((f) => f.id === id);
    if (folderIndex !== -1) {
        if (!newName || newName === folders.value[folderIndex].name) return;
        const oldName = folders.value[folderIndex].name;
        folders.value[folderIndex].name = newName;
        try {
            await updateHistoryFolder(id, newName, undefined);
        } catch {
            folders.value[folderIndex].name = oldName;
            error('Failed to rename folder');
        }
        return;
    }

    // Check if it's a graph
    const graphIndex = graphs.value.findIndex((g) => g.id === id);
    if (graphIndex !== -1) {
        if (!newName || newName === graphs.value[graphIndex].name) return;
        const oldName = graphs.value[graphIndex].name;
        graphs.value[graphIndex].name = newName;
        try {
            await updateGraphName(id, newName);
        } catch (err) {
            graphs.value[graphIndex].name = oldName;
            console.error('Error updating graph name:', err);
            error('Failed to update graph name. Please try again.', {
                title: 'Graph Rename Error',
            });
        }
    }
};

const cancelRename = () => {
    editingId.value = null;
    editInputValue.value = '';
};

const handleMoveGraph = async (
    graphId: string,
    folderId: string | null,
    workspaceId: string | null = null,
) => {
    const graph = graphs.value.find((g) => g.id === graphId);
    if (!graph) return;

    const oldFolderId = graph.folder_id;
    const oldWorkspaceId = graph.workspace_id;

    if (folderId) {
        graph.folder_id = folderId;
        const targetFolder = folders.value.find((f) => f.id === folderId);
        if (targetFolder) {
            graph.workspace_id = targetFolder.workspace_id;
        }
    } else if (workspaceId) {
        graph.folder_id = null;
        graph.workspace_id = workspaceId;
    } else {
        graph.folder_id = null;
    }

    try {
        await moveGraph(graphId, folderId, workspaceId);
        if (workspaceId) {
            await fetchData();
        }
    } catch {
        graph.folder_id = oldFolderId;
        graph.workspace_id = oldWorkspaceId;
        error('Failed to move graph.');
    }
};

const handleDeleteWorkspace = async () => {
    const ws = activeWorkspace.value;
    if (!ws) return;
    if (
        !confirm(
            `Delete workspace "${ws.name}"? Graphs inside will be moved to the "${workspaces.value[0].name}" workspace.`,
        )
    )
        return;

    if (workspaces.value.length <= 1) {
        error('Cannot delete the only workspace.');
        return;
    }
    // Prevent deleting the default (first) workspace
    if (ws.id === workspaces.value[0].id) {
        error('Cannot delete the Default workspace.');
        return;
    }

    try {
        await deleteWorkspace(ws.id);
        workspaces.value = workspaces.value.filter((w) => w.id !== ws.id);
        graphs.value.forEach((g) => {
            if (g.workspace_id === ws.id) g.workspace_id = workspaces.value[0].id;
        });
        // Switch to default workspace
        activeWorkspaceId.value = workspaces.value[0].id;
    } catch {
        error('Failed to delete workspace.');
    }
};

const handleDeleteFolder = async (folderId: string) => {
    if (!confirm('Delete this folder? Graphs inside will be moved to the root list.')) return;
    try {
        await deleteHistoryFolder(folderId);
        folders.value = folders.value.filter((f) => f.id !== folderId);
        graphs.value.forEach((g) => {
            if (g.folder_id === folderId) g.folder_id = null;
        });
    } catch {
        error('Failed to delete folder.');
    }
};

const debouncedUpdateFolder = useDebounceFn(async (folderId: string, color: string) => {
    try {
        await updateHistoryFolder(folderId, undefined, color);
    } catch (err) {
        console.error('Error updating folder color:', err);
        error('Failed to update folder color.');
    }
}, 500);

const handleUpdateFolderColor = (folderId: string, color: string) => {
    const folder = folders.value.find((f) => f.id === folderId);
    if (folder) {
        (folder as Folder).color = color;
    }

    debouncedUpdateFolder(folderId, color);
};

const handleImportGraph = async (files: FileList) => {
    if (!files || files.length === 0) return;

    try {
        const fileData = await files[0].text();
        const importedGraph = await importGraph(fileData);

        if (importedGraph) {
            await fetchData();
            await nextTick();
            success('Graph imported successfully!', {
                title: 'Graph Import',
            });
            navigateToGraph(importedGraph.id, false);
        } else {
            console.warn('Import successful but no graph returned from API');
        }
    } catch (err) {
        console.error('Error importing graph:', err);
        error('Failed to import graph. Please ensure the file is valid.', {
            title: 'Graph Import Error',
        });
    }
};

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
const handlePin = (graphId: string) => {
    const graph = graphs.value.find((g) => g.id === graphId);
    if (graph) {
        togglePin(graphId, !graph.pinned).catch((err) => {
            console.error('Error toggling pin status:', err);
            error('Failed to update pin status.', { title: 'Pin Toggle Error' });
            return;
        });
        graph.pinned = !graph.pinned;
    }
};

const handleRegenerateTitle = (graphId: string, strategy: 'first' | 'all') => {
    graphEvents.emit('update-name', {
        graphId: graphId,
        name: '...',
    });
    regenerateTitle(graphId, strategy);
};

const setInputRef = (id: string, el: unknown) => {
    if (el) inputRefs.value.set(id, el as HTMLInputElement);
};

const checkOverflow = () => {
    if (historyListRef.value) {
        isOverflowing.value = historyListRef.value.scrollHeight > historyListRef.value.clientHeight;
    }
};
useResizeObserver(historyListRef, checkOverflow);

// --- Workspace Switching ---
const switchWorkspace = (direction: 'next' | 'prev') => {
    if (workspaces.value.length <= 1) return;

    const currentIndex = workspaces.value.findIndex((w) => w.id === activeWorkspaceId.value);
    if (currentIndex === -1) return;

    let newIndex = direction === 'next' ? currentIndex + 1 : currentIndex - 1;

    // Clamp index
    if (newIndex < 0) newIndex = 0;
    if (newIndex >= workspaces.value.length) newIndex = workspaces.value.length - 1;

    if (newIndex !== currentIndex) {
        activeWorkspaceId.value = workspaces.value[newIndex].id;
    }
};

const throttledSwitch = useThrottleFn((direction: 'next' | 'prev') => {
    switchWorkspace(direction);
}, 300);

const handleWheel = (event: WheelEvent) => {
    if (!event.shiftKey) return;

    const delta = Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY;

    if (Math.abs(delta) > 10) {
        throttledSwitch(delta > 0 ? 'next' : 'prev');
    }
};

watch(
    expandedFolders,
    (newFolders) => {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(Array.from(newFolders)));
        } catch (e) {
            console.error('Failed to save expanded folders to localStorage', e);
        }
    },
    { deep: true },
);

watch(
    activeWorkspaceId,
    (newId) => {
        if (newId) {
            try {
                localStorage.setItem(WORKSPACE_STORAGE_KEY, newId);
            } catch (e) {
                console.error('Failed to save active workspace to localStorage', e);
            }
        }
    },
    { immediate: false },
);

watch([graphs, folders], () => nextTick(checkOverflow), { deep: true });

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

onMounted(async () => {
    isMac.value = /Mac|iPhone|iPad|iPod/.test(navigator.userAgent);

    // Load expanded folders from localStorage
    try {
        const storedFolders = localStorage.getItem(STORAGE_KEY);
        if (storedFolders) {
            const parsedFolders = JSON.parse(storedFolders);
            if (Array.isArray(parsedFolders)) {
                expandedFolders.value = new Set(parsedFolders);
            }
        }
    } catch (e) {
        console.error('Failed to load expanded folders from localStorage', e);
        // Reset to default if storage is corrupted
        localStorage.removeItem(STORAGE_KEY);
    }

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

    nextTick(() => fetchData());
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
                title="Create new workspace"
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
