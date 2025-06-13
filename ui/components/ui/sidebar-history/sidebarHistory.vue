<script lang="ts" setup>
import type { Graph } from '@/types/graph';

// --- Stores ---
const chatStore = useChatStore();
const globalSettingsStore = useSettingsStore();

// --- State from Stores (Reactive Refs) ---
const { currentModel, lastOpenedChatId, openChatId } = storeToRefs(chatStore);
const { modelsSettings } = storeToRefs(globalSettingsStore);

// --- Actions/Methods from Stores ---
const { resetChatState } = chatStore;

// --- Composables ---
const { getGraphs, createGraph, updateGraphName, deleteGraph } = useAPI();

// --- Routing ---
const route = useRoute();

// --- Local State ---
const graphs = ref<Graph[]>([]);
const editingGraphId = ref<string | null>(null);
const editInputValue = ref<string>('');
const inputRefs = ref(new Map<string, HTMLInputElement>());

// --- Computed Properties ---
const currentGraphId = computed(() => route.params.id as string | undefined);

// --- Core Logic Functions ---
const fetchGraphs = async () => {
    try {
        const response = await getGraphs();
        graphs.value = response;
    } catch (error) {
        console.error('Error fetching graphs:', error);
    }
};

const createGraphHandler = async () => {
    try {
        const newGraph = await createGraph();
        if (newGraph) {
            graphs.value.unshift(newGraph);
            currentModel.value = modelsSettings.value.defaultModel;
            resetChatState();
            lastOpenedChatId.value = null;
            navigateToGraph(newGraph.id);
        }
    } catch (err) {
        console.error('Failed to create graph from component:', err);
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
    } catch (error) {
        console.error('Error updating graph name:', error);
        if (graphIndex !== -1 && originalGraph) {
            graphs.value[graphIndex].name = originalGraph.name;
        }
    }
};

const cancelRename = () => {
    editingGraphId.value = null;
    editInputValue.value = '';
};

const handleDeleteGraph = async (graphId: string) => {
    if (!confirm(`Are you sure you want to delete graph ${graphId}? This cannot be undone.`)) {
        return;
    }

    await deleteGraph(graphId);

    const graphIndex = graphs.value.findIndex((g) => g.id === graphId);
    if (graphIndex !== -1) {
        graphs.value.splice(graphIndex, 1);
    }

    // If the deleted graph is the current one, navigate to the first graph or home page
    if (currentGraphId.value === graphId) {
        resetChatState();
        lastOpenedChatId.value = null;
        openChatId.value = null;
        const firstGraph = graphs.value[0];
        if (firstGraph) {
            navigateToGraph(firstGraph.id);
        } else {
            navigateTo('/');
        }
    }
};

// --- Lifecycle Hooks ---
onMounted(() => {
    nextTick(() => {
        fetchGraphs();
    });
});
</script>

<template>
    <div
        class="bg-anthracite/75 border-stone-gray/10 absolute top-2 left-2 z-10 flex h-[calc(100%-1rem)] w-[25rem]
            flex-col rounded-2xl border-2 px-4 pt-10 pb-4 shadow-lg backdrop-blur-md"
    >
        <UiSidebarHistoryLogo />
        <div
            class="bg-stone-gray/25 text-stone-gray font-outfit hover:bg-stone-gray/20 flex h-14 shrink-0
                cursor-pointer items-center space-x-2 rounded-xl px-5 font-bold transition duration-200 ease-in-out"
            role="button"
            @click="createGraphHandler"
        >
            <UiIcon name="Fa6SolidPlus" class="text-stone-gray h-4 w-4" />
            <span>New Canvas</span>
        </div>

        <div
            class="hide-scrollbar mt-4 flex h-full w-full flex-col items-center justify-start space-y-2 overflow-y-auto"
        >
            <div
                v-show="graphs.length === 0"
                class="text-stone-gray/50 mt-4 flex animate-pulse justify-center text-sm font-bold"
            >
                Loading history...
            </div>
            <div
                v-for="graph in graphs"
                :key="graph.id"
                class="flex w-full max-w-full cursor-pointer items-center justify-between rounded-lg py-2 pr-2 pl-4
                    transition-colors duration-300 ease-in-out"
                :class="{
                    'bg-obsidian text-stone-gray': graph.id === currentGraphId,
                    'bg-stone-gray hover:bg-stone-gray/80 text-obsidian':
                        graph.id !== currentGraphId,
                }"
                @click="() => navigateToGraph(graph.id)"
                role="button"
            >
                <div class="flex h-6 min-w-0 grow-1 items-center space-x-2">
                    <div
                        v-show="graph.id === currentGraphId && editingGraphId !== graph.id"
                        class="bg-terracotta-clay mr-2 h-2 w-4 rounded-full"
                    ></div>

                    <div v-if="editingGraphId === graph.id" class="flex items-center space-x-2">
                        <UiIcon
                            name="MaterialSymbolsEditRounded"
                            class="text-terracotta-clay h-4 w-4"
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

                    <span v-else class="truncate font-bold">
                        {{ graph.name }}
                    </span>
                </div>

                <UiSidebarHistoryActions
                    :graph="graph"
                    :currentGraphId="currentGraphId"
                    :renameGraph="handleStartRename"
                    :deleteGraph="handleDeleteGraph"
                />
            </div>
        </div>

        <button
            class="bg-stone-gray/10 hover:bg-stone-gray/15 hover:border-stone-gray/20 flex w-full cursor-pointer
                items-center justify-center gap-2 rounded-lg border-2 border-transparent py-2 pr-2 pl-4
                transition-colors duration-300 ease-in-out"
            @click="navigateTo('/settings')"
        >
            <UiIcon
                v-if="graphs.length > 0"
                name="MaterialSymbolsSettingsRounded"
                class="text-stone-gray h-6 w-6"
            />
            <span class="text-stone-gray font-bold">Settings</span>
        </button>
    </div>
</template>

<style scoped></style>
