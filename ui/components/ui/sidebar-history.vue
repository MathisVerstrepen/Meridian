<script lang="ts" setup>
import type { Graph } from '@/types/graph';

const { getGraphs, createGraph } = useAPI();
const router = useRouter();
const route = useRoute();

const currentGraphId = computed(() => route.params.id as string | undefined);
const graphs = ref<Graph[]>([]);

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
    router.push(`/graph/${id}`);
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
            class="bg-stone-gray/25 text-stone-gray font-outfit hover:bg-stone-gray/20 flex h-14 cursor-pointer
                items-center space-x-2 rounded-xl px-5 font-bold transition duration-200 ease-in-out"
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
            class="mt-4 flex w-full flex-col items-center justify-start space-y-2 overflow-y-auto"
        >
            <div
                v-for="graph in graphs"
                :key="graph.id"
                class="flex w-full cursor-pointer items-center justify-between rounded-lg px-4 py-2 transition-colors
                    duration-300 ease-in-out"
                :class="{
                    'bg-obsidian text-stone-gray': graph.id === currentGraphId,
                    'bg-stone-gray hover:bg-stone-gray/80 text-obsidian':
                        graph.id !== currentGraphId,
                }"
                @click="() => navigateToGraph(graph.id)"
                role="button"
            >
                <div class="flex items-center space-x-2">
                    <div
                        v-show="graph.id === currentGraphId"
                        class="bg-terracotta-clay h-2 w-2 rounded-full"
                    ></div>
                    <span class="font-bold">
                        {{ graph.name }}
                    </span>
                </div>

                <Icon
                    name="fa6-solid:ellipsis-vertical"
                    style="height: 1rem; width: 0.75rem"
                    class="transition-colors duration-300 ease-in-out"
                    :class="{
                        'fill-soft-silk': graph.id === currentGraphId,
                        'fill-obsidian': graph.id !== currentGraphId,
                    }"
                />
            </div>
        </div>
    </div>
</template>

<style scoped></style>
