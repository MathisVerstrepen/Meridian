<script lang="ts" setup>
import type { Graph, Folder } from '@/types/graph';
import { useResizeObserver } from '@vueuse/core';
import SidebarHistoryItem from './sidebarHistoryItem.vue';

// --- Stores ---
const chatStore = useChatStore();
const globalSettingsStore = useSettingsStore();
const sidebarCanvasStore = useSidebarCanvasStore();

// --- State from Stores (Reactive Refs) ---
const { upcomingModelData, lastOpenedChatId, openChatId } = storeToRefs(chatStore);
const { modelsSettings } = storeToRefs(globalSettingsStore);
const { isLeftOpen } = storeToRefs(sidebarCanvasStore);

// --- Actions/Methods from Stores ---
const { resetChatState } = chatStore;
const { toggleLeftSidebar } = sidebarCanvasStore;

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
} = useAPI();

const graphEvents = useGraphEvents();
const { error, success } = useToast();

// --- Local State ---
const graphs = ref<Graph[]>([]);
const folders = ref<Folder[]>([]);
const expandedFolders = ref<Set<string>>(new Set());
const searchQuery = ref('');

const editingId = ref<string | null>(null);
const editInputValue = ref<string>('');
const inputRefs = ref(new Map<string, HTMLInputElement>());

const historyListRef: Ref<HTMLDivElement | null> = ref(null);
const searchInputRef = ref<HTMLInputElement | null>(null);
const isOverflowing = ref(false);
const isMac = ref(false);
const isTemporaryOpen = computed(() => route.query.temporary === 'true');
const currentGraphId = computed(() => route.params.id as string | undefined);
const { handleDeleteGraph } = useGraphDeletion(graphs, currentGraphId);

// --- Computed Properties ---
const searchResults = computed(() => {
    if (!searchQuery.value) return [];
    return graphs.value
        .filter((graph) => graph.name.toLowerCase().includes(searchQuery.value.toLowerCase()))
        .sort((a, b) => Number(b.pinned) - Number(a.pinned));
});

const organizedData = computed(() => {
    if (searchQuery.value) return null;

    const pinned = graphs.value.filter((g) => g.pinned);
    const unpinned = graphs.value.filter((g) => !g.pinned);

    const folderMap = folders.value
        .map((folder) => ({
            ...folder,
            graphs: unpinned
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
        const [graphsData, foldersData] = await Promise.all([getGraphs(), getHistoryFolders()]);
        graphs.value = graphsData;
        folders.value = foldersData;
    } catch (err) {
        console.error('Error fetching data:', err);
        error('Failed to load history.', { title: 'Load Error' });
    }
};

const createGraphHandler = async () => {
    try {
        const newGraph = await createGraph(false);
        if (newGraph) {
            graphs.value.unshift(newGraph);
            upcomingModelData.value.data.model = modelsSettings.value.defaultModel;
            navigateToGraph(newGraph.id, false);
        }
    } catch (err) {
        console.error('Failed to create graph from component:', err);
        error('Failed to create new canvas. Please try again.', {
            title: 'Graph Creation Error',
        });
    }
};

const createTemporaryGraphHandler = async () => {
    try {
        const newGraph = await createGraph(true);
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
        const newFolder = await createHistoryFolder('New Folder');
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
            await updateHistoryFolder(id, newName);
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

const handleMoveGraph = async (graphId: string, folderId: string | null) => {
    const graph = graphs.value.find((g) => g.id === graphId);
    if (!graph) return;

    const oldFolderId = graph.folder_id;
    graph.folder_id = folderId;

    try {
        await moveGraph(graphId, folderId);
    } catch {
        graph.folder_id = oldFolderId;
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

const handleShiftSpace = () => document.execCommand('insertText', false, ' ');

const handleImportGraph = async (files: FileList) => {
    if (!files || files.length === 0) return;

    try {
        const fileData = await files[0].text();
        const importedGraph = await importGraph(fileData);
        if (importedGraph) {
            await getGraphs();
            await nextTick();
            success('Graph imported successfully!', {
                title: 'Graph Import',
            });
            navigateToGraph(importedGraph.id, false);
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
        searchInputRef.value?.focus();
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

const setInputRef = (id: string, el: unknown) => {
    if (el) inputRefs.value.set(id, el as HTMLInputElement);
};

const checkOverflow = () => {
    if (historyListRef.value) {
        isOverflowing.value = historyListRef.value.scrollHeight > historyListRef.value.clientHeight;
    }
};
useResizeObserver(historyListRef, checkOverflow);
watch([graphs, folders], () => nextTick(checkOverflow), { deep: true });

onMounted(async () => {
    isMac.value = /Mac|iPhone|iPad|iPod/.test(navigator.userAgent);

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
    >
        <UiSidebarHistoryLogo class="hide-close" />

        <div class="hide-close flex items-center gap-2">
            <!-- New canvas button -->
            <div
                class="dark:bg-stone-gray/25 bg-obsidian/50 text-stone-gray font-outfit
                    dark:hover:bg-stone-gray/20 hover:bg-obsidian/75 flex h-14 shrink-0 grow
                    cursor-pointer items-center space-x-2 rounded-xl pr-3 pl-5 font-bold transition
                    duration-200 ease-in-out"
                role="button"
                :title="`Create New Canvas (${isMac ? '⌘' : 'ALT'} + N)`"
                @click="createGraphHandler"
            >
                <UiIcon name="Fa6SolidPlus" class="text-stone-gray h-4 w-4" />
                <span>New Canvas</span>
                <div
                    class="text-stone-gray/30 ml-auto rounded-md border px-1 py-0.5 text-[10px]
                        font-bold"
                >
                    {{ isMac ? '⌘ + N' : 'ALT + N' }}
                </div>
            </div>

            <!-- New Folder Button -->
            <button
                class="dark:bg-stone-gray/25 bg-obsidian/50 text-stone-gray
                    dark:hover:bg-stone-gray/20 hover:bg-obsidian/75 flex h-14 w-14 items-center
                    justify-center rounded-xl transition duration-200 ease-in-out
                    hover:cursor-pointer"
                title="Create New Folder"
                @click="createFolderHandler"
            >
                <UiIcon name="MdiFolderPlusOutline" class="h-5 w-5" />
            </button>

            <!-- Temporary chat button -->
            <button
                class="flex h-14 w-14 items-center justify-center rounded-xl transition duration-200
                    ease-in-out hover:cursor-pointer"
                :class="{
                    'bg-ember-glow/20 border-ember-glow/50 text-ember-glow border-2':
                        isTemporaryOpen,
                    [`dark:bg-stone-gray/25 bg-obsidian/50 text-stone-gray
                    dark:hover:bg-stone-gray/20 hover:bg-obsidian/75`]: !isTemporaryOpen,
                }"
                title="New temporary chat (no save)"
                @click="createTemporaryGraphHandler"
            >
                <UiIcon name="LucideMessageCircleDashed" class="h-5 w-5" />
            </button>
        </div>

        <div class="hide-close mt-2 flex items-center gap-2">
            <div class="relative w-full">
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
            <label
                class="dark:bg-stone-gray/25 bg-obsidian/50 text-stone-gray font-outfit
                    dark:hover:bg-stone-gray/20 hover:bg-obsidian/75 flex h-9 w-14 shrink-0
                    items-center justify-center rounded-xl transition duration-200 ease-in-out
                    hover:cursor-pointer"
                title="Import Canvas Backup"
            >
                <UiIcon name="UilUpload" class="text-stone-gray h-5 w-5" />
                <input
                    type="file"
                    multiple
                    class="hidden"
                    @change="
                        (e) => {
                            const target = e.target as HTMLInputElement;
                            if (target.files) handleImportGraph(target.files);
                        }
                    "
                />
            </label>
        </div>

        <div
            ref="historyListRef"
            class="hide-close hide-scrollbar relative mt-4 flex grow flex-col space-y-2
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
                <SidebarHistoryItem
                    v-for="graph in searchResults"
                    :key="graph.id"
                    :graph="graph"
                    :current-graph-id="currentGraphId"
                    :editing-id="editingId"
                    :edit-input-value="editInputValue"
                    :folders="folders"
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
                />
            </template>

            <template v-else-if="organizedData">
                <!-- PINNED CANVAS -->
                <div v-if="organizedData.pinned.length > 0" class="space-y-2">
                    <SidebarHistoryItem
                        v-for="graph in organizedData.pinned"
                        :key="graph.id"
                        :graph="graph"
                        :current-graph-id="currentGraphId"
                        :editing-id="editingId"
                        :edit-input-value="editInputValue"
                        :folders="folders"
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
                    />
                </div>

                <!-- FOLDERS CANVAS -->
                <div v-for="folder in organizedData.folders" :key="folder.id">
                    <div
                        class="group flex w-full cursor-pointer items-center justify-between
                            rounded-lg py-1.5 pr-2 pl-4 transition-colors duration-200"
                        :class="{
                            'dark:bg-stone-gray/10 bg-obsidian/5 mb-2': expandedFolders.has(
                                folder.id,
                            ),
                            'bg-stone-gray/5 hover:dark:bg-stone-gray/10 hover:bg-obsidian/5':
                                !expandedFolders.has(folder.id),
                        }"
                        @click="toggleFolder(folder.id)"
                    >
                        <div
                            class="flex min-w-0 grow items-center space-x-2 overflow-hidden"
                            @dblclick.stop="handleStartRename(folder.id, folder.name)"
                        >
                            <UiIcon
                                name="MdiFolderOutline"
                                class="h-4 w-4 shrink-0 transition-transform duration-200"
                                :class="{
                                    'text-ember-glow': expandedFolders.has(folder.id),
                                    'text-stone-gray/70': !expandedFolders.has(folder.id),
                                }"
                            />
                            <div v-if="editingId === folder.id" class="flex grow items-center">
                                <input
                                    :ref="(el) => setInputRef(folder.id, el)"
                                    v-model="editInputValue"
                                    type="text"
                                    class="bg-anthracite/20 text-stone-gray w-full rounded px-1
                                        text-sm font-bold outline-none"
                                    @click.stop
                                    @keydown.enter.prevent="confirmRename"
                                    @keydown.esc.prevent="cancelRename"
                                    @blur="confirmRename"
                                />
                            </div>
                            <span v-else class="text-stone-gray truncate text-sm font-bold">{{
                                folder.name
                            }}</span>
                            <div
                                class="text-stone-gray/50 bg-obsidian/20 rounded-full px-2 py-1
                                    font-mono text-xs"
                            >
                                {{ folder.graphs.length }}
                            </div>
                        </div>

                        <div class="opacity-0 transition-opacity group-hover:opacity-100">
                            <button
                                class="hover:text-terracotta-clay text-stone-gray/50 flex
                                    items-center justify-center px-1 py-2"
                                title="Delete Folder"
                                @click.stop="handleDeleteFolder(folder.id)"
                            >
                                <UiIcon name="MaterialSymbolsDeleteRounded" class="h-4 w-4" />
                            </button>
                        </div>
                    </div>

                    <div
                        v-show="expandedFolders.has(folder.id)"
                        class="border-stone-gray/10 ml-4 space-y-2 border-l pl-2"
                    >
                        <div
                            v-if="folder.graphs.length === 0"
                            class="text-stone-gray/40 py-1 pl-2 text-xs italic"
                        >
                            Empty
                        </div>
                        <SidebarHistoryItem
                            v-for="graph in folder.graphs"
                            :key="graph.id"
                            :graph="graph"
                            :current-graph-id="currentGraphId"
                            :editing-id="editingId"
                            :edit-input-value="editInputValue"
                            :folders="folders"
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
                        />
                    </div>
                </div>

                <!-- LOOSE CANVAS -->
                <div class="space-y-2">
                    <SidebarHistoryItem
                        v-for="graph in organizedData.loose"
                        :key="graph.id"
                        :graph="graph"
                        :current-graph-id="currentGraphId"
                        :editing-id="editingId"
                        :edit-input-value="editInputValue"
                        :folders="folders"
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
                    />
                </div>
            </template>
        </div>

        <div
            v-show="isOverflowing"
            class="hide-close pointer-events-none absolute bottom-[80px] left-0 h-10 w-full px-4"
        >
            <div
                class="dark:from-anthracite/75 from-stone-gray/20 absolute z-10 h-10 w-[364px]
                    bg-gradient-to-t to-transparent"
            />
            <div class="from-obsidian absolute h-10 w-[364px] bg-gradient-to-t to-transparent" />
        </div>

        <UiSidebarHistoryUserProfileCard />
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
