<script lang="ts" setup>
import type { Graph } from '@/types/graph';

// --- Page Meta ---
definePageMeta({ layout: 'blank' });
useHead({
    title: 'Meridian - Home',
});

// --- Stores ---
const chatStore = useChatStore();
const globalSettingsStore = useGlobalSettingsStore();

// --- State from Stores (Reactive Refs) ---
const { isOpen: isChatOpen, currentModel } = storeToRefs(chatStore);
const { defaultModel } = globalSettingsStore;

// --- Actions/Methods from Stores ---
const { resetChatState } = chatStore;

// --- Composables ---
const { getGraphs, createGraph } = useAPI();

// --- Local State ---
const graphs = ref<Graph[]>([]);

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
            currentModel.value = defaultModel;
            isChatOpen.value = false;
            resetChatState();
            navigateTo(`graph/${newGraph.id}`);
        }
    } catch (err) {
        console.error('Failed to create graph from component:', err);
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
    <div class="bg-anthracite h-full w-full">
        <div class="flex h-[60%] w-full flex-col items-center justify-center">
            <h1 class="font-outfit text-soft-silk mb-16 text-5xl font-bold">
                <span class="text-terracotta-clay">Hello World !</span> What can I do for you ?
            </h1>

            <UiChatTextInput @trigger-scroll="() => {}" @generate="() => {}"></UiChatTextInput>

            <p class="font-outfit text-soft-silk/50 my-5 font-bold">OR</p>

            <div class="flex w-full justify-center gap-4">
                <button
                    class="bg-terracotta-clay/10 border-terracotta-clay-dark/50 hover:bg-terracotta-clay/20 flex cursor-pointer
                        items-center gap-2 rounded-3xl border-2 px-10 py-4 transition duration-200 ease-in-out"
                    @click="createGraphHandler"
                >
                    <UiIcon name="Fa6SolidPlus" class="text-soft-silk h-6 w-6 opacity-80" />
                    <span class="text-soft-silk/80 text-lg font-bold">Create new canvas</span>
                </button>

                <button
                    class="bg-obsidian/20 border-obsidian/50 hover:bg-obsidian/40 flex cursor-pointer items-center gap-2
                        rounded-3xl border-2 px-10 py-4 transition duration-200 ease-in-out"
                >
                    <UiIcon
                        name="MaterialSymbolsAndroidChat"
                        class="text-soft-silk h-6 w-6 opacity-80"
                    />
                    <span class="text-soft-silk/80 text-lg font-bold">Open new chat</span>
                </button>
            </div>
        </div>

        <div
            class="bg-obsidian/50 mx-auto flex h-[40%] w-[98%] flex-col items-center rounded-t-3xl p-8 backdrop-blur"
        >
            <h2 class="font-outfit text-stone-gray mb-8 text-xl font-bold">Recent Canvas</h2>
            <div class="grid h-full w-full auto-rows-[10rem] grid-cols-4 gap-4 overflow-y-auto">
                <NuxtLink
                    v-for="graph in graphs"
                    :key="graph.id"
                    class="bg-obsidian/70 hover:bg-obsidian border-obsidian flex h-40 w-full cursor-pointer items-center
                        justify-between rounded-2xl border-2 py-2 pr-2 pl-4 transition-colors duration-200 ease-in-out"
                    role="button"
                    :to="{ name: 'graph-id', params: { id: graph.id } }"
                >
                    <div class="flex grow-1 flex-col items-center">
                        <span class="text-stone-gray text-lg font-bold">
                            {{ graph.name }}
                        </span>
                        <NuxtTime
                            :datetime="new Date(graph.updated_at)"
                            class="text-stone-gray"
                            locale="en-US"
                            year="numeric"
                            month="2-digit"
                            day="2-digit"
                        />
                    </div>
                </NuxtLink>
            </div>
        </div>
    </div>
</template>

<style scoped></style>
