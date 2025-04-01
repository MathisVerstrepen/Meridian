<script lang="ts" setup>
import type { Graph } from '@/types/graph';

const { getGraphs, createGraph, updateGraphName } = useAPI();
const router = useRouter();
const route = useRoute();

const currentGraphId = computed(() => route.params.id as string | undefined);
const graphs = ref<Graph[]>([]);

const editingGraphId = ref<string | null>(null);
const editInputValue = ref<string>('');
const inputRefs = ref(new Map<string, HTMLInputElement>());

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
    router.push(`/graph/${id}`);
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
        console.log(`Updating graph ${graphIdToUpdate} name to: ${newName}`);
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

    // TODO: Implement delete graph functionality
    console.log('Delete graph:', graphId);
};

onMounted(() => {
    fetchGraphs();
});
</script>

<template>
    <div
        class="bg-anthracite/75 border-stone-gray/10 absolute top-2 left-2 z-10 flex h-[calc(100%-1rem)] w-[25rem]
            flex-col rounded-2xl border-2 px-4 py-10 shadow-lg backdrop-blur-md"
    >
        <div class="text-stone-gray font-outfit mb-8 w-full text-center text-4xl font-bold">
            Meridian <span class="text-terracotta-clay">AI</span>
        </div>
        <div
            class="bg-stone-gray/25 text-stone-gray font-outfit hover:bg-stone-gray/20 flex h-14 shrink-0
                cursor-pointer items-center space-x-2 rounded-xl px-5 font-bold transition duration-200 ease-in-out"
            role="button"
            @click="createGraphHandler"
        >
            <Icon
                name="fa6-solid:plus"
                style="color: var(--color-stone-gray); height: 1rem; width: 1rem"
            />
            <span>New Canvas</span>
        </div>

        <div
            v-if="graphs.length"
            class="mt-4 flex h-full w-full flex-col items-center justify-start space-y-2 overflow-y-auto"
        >
            <div
                v-for="graph in graphs"
                :key="graph.id"
                class="flex w-full cursor-pointer items-center justify-between rounded-lg py-2 pr-2 pl-4 transition-colors
                    duration-300 ease-in-out"
                :class="{
                    'bg-obsidian text-stone-gray': graph.id === currentGraphId,
                    'bg-stone-gray hover:bg-stone-gray/80 text-obsidian':
                        graph.id !== currentGraphId,
                }"
                @click="() => navigateToGraph(graph.id)"
                role="button"
            >
                <div class="flex h-6 items-center space-x-2">
                    <div
                        v-show="graph.id === currentGraphId && editingGraphId !== graph.id"
                        class="bg-terracotta-clay mr-2 h-2 w-4 rounded-full"
                    ></div>

                    <div v-if="editingGraphId === graph.id" class="flex items-center space-x-2">
                        <Icon
                            name="material-symbols:edit-rounded"
                            class="text-terracotta-clay"
                            style="height: 1rem; width: 1rem"
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
        <div v-else class="text-stone-gray/50 mt-4 flex justify-center">Loading graphs...</div>
    </div>
</template>

<style scoped></style>
