<script lang="ts" setup>
const router = useRouter();
const graphHistoryStore = useGraphHistoryStore();

const { graphs, error } = storeToRefs(graphHistoryStore);

onMounted(() => {
    graphHistoryStore.fetchGraphsIfNeeded();
});

const createGraphHandler = async () => {
    try {
        const newGraph = await graphHistoryStore.addGraph();
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
            class="bg-stone-gray/25 text-stone-gray font-outfit flex h-14 items-center space-x-2 rounded-xl px-5
                font-bold hover:bg-stone-gray/20 cursor-pointer transition duration-200 ease-in-out"
            role="button"
            @click="createGraphHandler"
        >
            <Icon
                name="fa6-solid:plus"
                style="color: var(--color-stone-gray); height: 1rem; width: 1rem"
            />
            <span>New Canvas</span>
        </div>

        <div class="mt-4 flex w-full flex-col items-center justify-start space-y-2 overflow-y-auto">
            <div
                v-for="graph in graphs"
                :key="graph.id"
                class="flex w-full items-center justify-between rounded-lg bg-stone-gray py-2 px-4
                     hover:bg-stone-gray/80 cursor-pointer transition duration-200 ease-in-out"
                @click="() => navigateToGraph(graph.id)"
                role="button"
            >
                <span class="font-bold text-obsidian">
                    {{ graph.name }}
                </span>
                <Icon
                    name="fa6-solid:ellipsis-vertical"
                    style="color: var(--color-obsidian); height: 1rem; width: 1rem"
                />
            </div>
        </div>
    </div>
</template>

<style scoped></style>
