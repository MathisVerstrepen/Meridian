<script lang="ts" setup>
const { getGraphs, createGraph } = useAPI();
import type { Graph } from "@/types/graph";

const graphs = ref<Graph[]>([]);

onMounted(async () => {
    try {
        const response = await getGraphs();
        graphs.value = response;
    } catch (error) {
        console.error("Error fetching graphs:", error);
    }
});

const createGraphHandler = async () => {
    try {
        const response = await createGraph();
        graphs.value.push(response);
    } catch (error) {
        console.error("Error creating graph:", error);
    }
};

const navigateToGraph = (id: string) => {
    const router = useRouter();
    router.push(`/graph/${id}`);
};
</script>

<template>
    <div
        class="flex flex-col items-center justify-center h-full w-full relative"
    >
        <div class="flex flex-col items-center justify-center w-96">
            <h1 class="text-2xl font-bold text-gray-800 mb-4">Graphs</h1>
            <ul class="w-full h-96 overflow-y-auto m-4">
                <li
                    v-for="graph in graphs"
                    :key="graph.id"
                    class="mb-2 bg-white rounded-lg p-4 shadow-md flex items-center justify-between"
                >
                    <span class="text-lg font-bold text-gray-800">
                        {{ graph.name }}
                    </span>
                    <button
                        class="bg-blue-500 text-white px-4 py-2 rounded-lg shadow-lg"
                        @click="() => navigateToGraph(graph.id)"
                    >
                        Open
                    </button>
                </li>
            </ul>
        </div>

        <button
            class="bg-blue-500 text-white px-4 py-2 rounded-lg shadow-lg"
            @click="createGraphHandler"
        >
            New Graph
        </button>
    </div>
</template>

<style scoped></style>
