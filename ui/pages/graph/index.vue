<script lang="ts" setup>
const { getGraphs, createGraph } = useAPI();
import type { Graph } from '@/types/graph';

const graphs = ref<Graph[]>([]);

const createGraphHandler = async () => {
    try {
        const response = await createGraph();
        graphs.value.push(response);
    } catch (error) {
        console.error('Error creating graph:', error);
    }
};

const navigateToGraph = (id: string) => {
    const router = useRouter();
    router.push(`/graph/${id}`);
};

onMounted(() => {
    nextTick(async () => {
        try {
            const response = await getGraphs();
            graphs.value = response;
        } catch (error) {
            console.error('Error fetching graphs:', error);
        }
    });
});
</script>

<template>
    <div class="relative flex h-full w-full flex-col items-center justify-center">
        <div class="flex w-96 flex-col items-center justify-center">
            <h1 class="mb-4 text-2xl font-bold text-gray-800">Graphs</h1>
            <ul class="m-4 h-96 w-full overflow-y-auto">
                <li
                    v-for="graph in graphs"
                    :key="graph.id"
                    class="mb-2 flex items-center justify-between rounded-lg bg-white p-4 shadow-md"
                >
                    <span class="text-lg font-bold text-gray-800">
                        {{ graph.name }}
                    </span>
                    <button
                        class="rounded-lg bg-blue-500 px-4 py-2 text-white shadow-lg"
                        @click="() => navigateToGraph(graph.id)"
                    >
                        Open
                    </button>
                </li>
            </ul>
        </div>

        <button
            class="rounded-lg bg-blue-500 px-4 py-2 text-white shadow-lg"
            @click="createGraphHandler"
        >
            New Graph
        </button>
    </div>
</template>

<style scoped></style>
