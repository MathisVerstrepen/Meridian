<script lang="ts" setup>
import type { Graph } from '@/types/graph';
import { useResizeObserver } from '@vueuse/core';

// --- Stores ---
const chatStore = useChatStore();
const globalSettingsStore = useSettingsStore();

// --- State from Stores (Reactive Refs) ---
const { currentModel, lastOpenedChatId, openChatId } = storeToRefs(chatStore);
const { modelsSettings } = storeToRefs(globalSettingsStore);

// --- Actions/Methods from Stores ---
const { resetChatState } = chatStore;

// --- Routing ---
const route = useRoute();

// --- Computed Properties ---
const currentGraphId = computed(() => route.params.id as string | undefined);

// --- Local State ---
const graphs = ref<Graph[]>([]);
const editingGraphId = ref<string | null>(null);
const editInputValue = ref<string>('');
const inputRefs = ref(new Map<string, HTMLInputElement>());
const historyListRef: Ref<HTMLDivElement | null> = ref(null);
const isOverflowing = ref(false);

// --- Composables ---
const { getGraphs, createGraph, updateGraphName, exportGraph, importGraph } = useAPI();
const graphEvents = useGraphEvents();
const { error, success } = useToast();
const { handleDeleteGraph } = useGraphDeletion(graphs, currentGraphId);

// --- Core Logic Functions ---
const fetchGraphs = async () => {
    try {
        const response = await getGraphs();
        graphs.value = response;
    } catch (err) {
        console.error('Error fetching graphs:', err);
        error('Failed to load graphs. Please try again later.', {
            title: 'Graph Load Error',
        });
    }
};

const createGraphHandler = async () => {
    try {
        const newGraph = await createGraph();
        if (newGraph) {
            graphs.value.unshift(newGraph);
            currentModel.value = modelsSettings.value.defaultModel;
            navigateToGraph(newGraph.id);
        }
    } catch (err) {
        console.error('Failed to create graph from component:', err);
        error('Failed to create new canvas. Please try again.', {
            title: 'Graph Creation Error',
        });
    }
};

const navigateToGraph = (id: string) => {
    if (id === editingGraphId.value) {
        return;
    }
    resetChatState();
    lastOpenedChatId.value = null;
    openChatId.value = null;
    navigateTo(`/graph/${id}`);
};

const handleStartRename = async (graphId: string) => {
    const graphToEdit = graphs.value.find((g) => g.id === graphId);
    if (graphToEdit) {
        editingGraphId.value = graphId;
        editInputValue.value = graphToEdit.name;

        await nextTick();

        const inputElement = inputRefs.value.get(graphId);
        if (inputElement) {
            inputElement.focus();
            inputElement.select();
        }
    }
};

const confirmRename = async () => {
    if (!editingGraphId.value) return;

    const graphIdToUpdate = editingGraphId.value;
    const newName = editInputValue.value.trim();

    editingGraphId.value = null;

    const originalGraph = graphs.value.find((g) => g.id === graphIdToUpdate);

    if (!newName || !originalGraph || newName === originalGraph.name) {
        editInputValue.value = '';
        return;
    }

    const graphIndex = graphs.value.findIndex((g) => g.id === graphIdToUpdate);
    if (graphIndex !== -1) {
        graphs.value[graphIndex].name = newName;
    }

    editInputValue.value = '';

    try {
        await updateGraphName(graphIdToUpdate, newName);
    } catch (err) {
        console.error('Error updating graph name:', err);
        error('Failed to update graph name. Please try again.', {
            title: 'Graph Rename Error',
        });
        if (graphIndex !== -1 && originalGraph) {
            graphs.value[graphIndex].name = originalGraph.name;
        }
    }
};

const cancelRename = () => {
    editingGraphId.value = null;
    editInputValue.value = '';
};

const handleImportGraph = async (files: FileList) => {
    if (!files || files.length === 0) return;

    try {
        const fileData = await files[0].text();
        const importedGraph = await importGraph(fileData);
        if (importedGraph) {
            await fetchGraphs();
            await nextTick();
            success('Graph imported successfully!', {
                title: 'Graph Import',
            });
            navigateToGraph(importedGraph.id);
        }
    } catch (err) {
        console.error('Error importing graph:', err);
        error('Failed to import graph. Please ensure the file is valid.', {
            title: 'Graph Import Error',
        });
    }
};

const handleKeyDown = (event: KeyboardEvent) => {
    if ((event.key === 'N' || event.key === 'n') && event.altKey) {
        event.preventDefault();
        createGraphHandler();
    }
};

// --- Watchers ---
const checkOverflow = () => {
    if (historyListRef.value) {
        isOverflowing.value = historyListRef.value.scrollHeight > historyListRef.value.clientHeight;
    }
};

useResizeObserver(historyListRef, checkOverflow);
watch(graphs, () => nextTick(checkOverflow), { deep: true });

// --- Lifecycle Hooks ---
onMounted(async () => {
    const unsubscribe = graphEvents.on(
        'update-name',
        async ({ graphId, name }: { graphId: string; name: string }) => {
            const graphToUpdate = graphs.value.find((g) => g.id === graphId);
            if (graphToUpdate) {
                graphToUpdate.name = name;
                await updateGraphName(graphId, name);
            }
        },
    );

    onUnmounted(unsubscribe);

    nextTick(() => {
        fetchGraphs();
    });

    document.addEventListener('keydown', handleKeyDown);
});

onUnmounted(() => {
    document.removeEventListener('keydown', handleKeyDown);
});
</script>

<template>
    <div
        class="dark:bg-anthracite/75 bg-stone-gray/20 border-stone-gray/10 absolute top-2 left-2 z-10 flex
            h-[calc(100%-1rem)] w-[25rem] flex-col rounded-2xl border-2 px-4 pt-10 pb-4 shadow-lg
            backdrop-blur-md"
    >
        <UiSidebarHistoryLogo />

        <div class="flex items-center gap-2">
            <div
                class="dark:bg-stone-gray/25 bg-obsidian/50 text-stone-gray font-outfit dark:hover:bg-stone-gray/20
                    hover:bg-obsidian/75 flex h-14 shrink-0 grow cursor-pointer items-center space-x-2 rounded-xl px-5
                    font-bold transition duration-200 ease-in-out"
                role="button"
                title="Create New Canvas (ALT + N)"
                @click="createGraphHandler"
            >
                <UiIcon name="Fa6SolidPlus" class="text-stone-gray h-4 w-4" />
                <span>New Canvas</span>
                <div
                    class="text-stone-gray/30 ml-auto rounded-md border px-1 py-0.5 text-[10px] font-bold"
                >
                    ALT + N
                </div>
            </div>
            <!-- Canvas backup upload -->
            <label
                class="dark:bg-stone-gray/25 bg-obsidian/50 text-stone-gray font-outfit dark:hover:bg-stone-gray/20
                    hover:bg-obsidian/75 flex h-14 w-14 items-center justify-center rounded-xl transition duration-200
                    ease-in-out hover:cursor-pointer"
            >
                <UiIcon name="UilUpload" class="text-stone-gray h-5 w-5" />
                <input
                    type="file"
                    multiple
                    class="hidden"
                    @change="
                        (e) => {
                            const target = e.target as HTMLInputElement;
                            if (target.files) {
                                handleImportGraph(target.files);
                            }
                        }
                    "
                />
            </label>
        </div>

        <div
            ref="historyListRef"
            class="hide-scrollbar relative mt-4 flex grow flex-col space-y-2 overflow-y-auto pb-2"
        >
            <div
                v-show="graphs.length === 0"
                class="text-stone-gray/50 mt-4 flex animate-pulse justify-center text-sm font-bold"
            >
                Loading user canvas...
            </div>
            <div
                v-for="graph in graphs"
                :key="graph.id"
                class="flex w-full max-w-full cursor-pointer items-center justify-between rounded-lg py-2 pr-2 pl-4
                    transition-colors duration-300 ease-in-out"
                :class="{
                    'dark:bg-obsidian bg-soft-silk dark:text-stone-gray text-obsidian':
                        graph.id === currentGraphId,
                    'dark:bg-stone-gray dark:hover:bg-stone-gray/80 dark:text-obsidian bg-obsidian text-soft-silk/80':
                        graph.id !== currentGraphId,
                }"
                role="button"
                @click="() => navigateToGraph(graph.id)"
            >
                <div
                    class="flex h-6 min-w-0 grow-1 items-center space-x-2"
                    @dblclick.stop="handleStartRename(graph.id)"
                >
                    <div
                        v-show="graph.id === currentGraphId && editingGraphId !== graph.id"
                        class="bg-ember-glow/80 mr-2 h-2 w-4 shrink-0 rounded-full"
                    />

                    <div v-if="editingGraphId === graph.id" class="flex items-center space-x-2">
                        <UiIcon
                            name="MaterialSymbolsEditRounded"
                            class="text-ember-glow/80 h-4 w-4"
                            aria-hidden="true"
                        />
                        <input
                            :ref="
                                (el) => {
                                    if (el) inputRefs.set(graph.id, el as any);
                                }
                            "
                            v-model="editInputValue"
                            type="text"
                            class="w-full rounded px-2 font-bold outline-none"
                            :class="{
                                'bg-stone-gray/20': graph.id === currentGraphId,
                                'bg-anthracite/20': graph.id !== currentGraphId,
                            }"
                            @click.stop
                            @keydown.enter.prevent="confirmRename"
                            @keydown.esc.prevent="cancelRename"
                            @blur="confirmRename"
                        />
                    </div>

                    <span v-else class="truncate font-bold" :title="graph.name">
                        {{ graph.name }}
                    </span>
                </div>

                <UiSidebarHistoryActions
                    :graph="graph"
                    :current-graph-id="currentGraphId"
                    @rename="handleStartRename"
                    @delete="
                        (graphId: string, graphName: string) =>
                            handleDeleteGraph(graphId, graphName, true)
                    "
                    @download="exportGraph"
                />
            </div>
        </div>

        <!-- Gradient Overlay when overflowing y-axis -->
        <div
            v-show="isOverflowing"
            class="pointer-events-none absolute bottom-17 left-0 h-10 w-full px-4"
        >
            <div
                class="dark:from-anthracite/75 from-stone-gray/20 absolute z-10 h-10 w-[364px] bg-gradient-to-t
                    to-transparent"
            />
            <div class="from-obsidian absolute h-10 w-[364px] bg-gradient-to-t to-transparent" />
        </div>

        <button
            class="dark:bg-stone-gray/10 dark:hover:bg-stone-gray/15 dark:hover:border-stone-gray/20
                dark:text-stone-gray text-soft-silk bg-anthracite hover:bg-stone-gray/10 hover:border-soft-silk/10
                mt-2 flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg border-2
                border-transparent py-2 pr-2 pl-4 transition-colors duration-300 ease-in-out"
            @click="navigateTo('/settings')"
        >
            <UiIcon name="MaterialSymbolsSettingsRounded" class="h-6 w-6" />
            <span class="font-bold">Settings</span>
        </button>
    </div>
</template>

<style scoped></style>
