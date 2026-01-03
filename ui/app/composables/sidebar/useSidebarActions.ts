import type { Graph, Folder, Workspace } from '@/types/graph';
import { useDebounceFn } from '@vueuse/core';
import { PLAN_LIMITS } from '@/constants/limits';
import type { User } from '@/types/user';

export const useSidebarActions = (
    graphs: Ref<Graph[]>,
    folders: Ref<Folder[]>,
    activeWorkspace: Ref<Workspace | undefined>,
    expandedFolders: Ref<Set<string>>,
    fetchData: () => Promise<void>,
) => {
    const {
        createGraph,
        createHistoryFolder,
        updateGraphName,
        updateHistoryFolder,
        moveGraph,
        deleteHistoryFolder,
        togglePin,
        importGraph,
        exportGraph,
    } = useAPI();

    const { user } = useUserSession();
    const { error, success } = useToast();
    const chatStore = useChatStore();
    const globalSettingsStore = useSettingsStore();
    const streamStore = useStreamStore();
    const graphEvents = useGraphEvents();
    const { upcomingModelData, lastOpenedChatId, openChatId } = storeToRefs(chatStore);
    const { modelsSettings } = storeToRefs(globalSettingsStore);
    const { resetChatState } = chatStore;
    const { regenerateTitle } = streamStore;

    // --- Local State for Editing ---
    const editingId = ref<string | null>(null);
    const editInputValue = ref<string>('');
    const inputRefs = ref(new Map<string, HTMLInputElement>());

    // --- Helpers ---
    const isLimitReached = computed(() => {
        if ((user.value as User)?.plan_type !== 'free') return false;
        const nonTemporaryGraphs = graphs.value.filter((g) => !g.temporary);
        return nonTemporaryGraphs.length >= PLAN_LIMITS.FREE.MAX_GRAPHS;
    });

    const navigateToGraph = (id: string, temporary: boolean) => {
        if (id === editingId.value) return;
        resetChatState();
        lastOpenedChatId.value = null;
        openChatId.value = null;
        navigateTo(`/graph/${id}?temporary=${temporary}`);
    };

    // --- Actions ---
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
            console.error('Failed to create graph:', err);
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
            console.error('Failed to create temporary graph:', err);
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
            console.error('Failed to create folder:', err);
            error('Failed to create new folder. Please try again.', {
                title: 'Folder Creation Error',
            });
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
            folder.color = color;
        }
        debouncedUpdateFolder(folderId, color);
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

    const handleImportGraph = async (files: FileList) => {
        if (!files || files.length === 0) return;
        try {
            const fileData = await files[0].text();
            const importedGraph = await importGraph(fileData);
            if (importedGraph) {
                await fetchData();
                await nextTick();
                success('Graph imported successfully!', { title: 'Graph Import' });
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

    const setInputRef = (id: string, el: unknown) => {
        if (el) inputRefs.value.set(id, el as HTMLInputElement);
    };

    return {
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
    };
};
