<script lang="ts" setup>
import type { Graph } from '@/types/graph';

const selectedTab = defineModel('selectedTab', {
    type: Number,
    default: 0,
});

const props = defineProps<{
    graph: Graph | null;
    isTemporary: boolean;
    selectedNodeId: string | null;
}>();

// --- Stores ---
const sidebarCanvasStore = useSidebarCanvasStore();
const chatStore = useChatStore();

// --- State from Stores (Reactive Refs) ---
const { isRightOpen } = storeToRefs(sidebarCanvasStore);
const { openChatId } = storeToRefs(chatStore);

// --- Actions/Methods from Stores ---
const { toggleRightSidebar } = sidebarCanvasStore;

// --- Composables ---
const graphEvents = useGraphEvents();

const nodeId = ref<string | null>(props.selectedNodeId);

// --- Core Logic Functions ---
const changeTab = (index: number) => {
    selectedTab.value = index;
};

// --- Watchers ---
watch(
    () => props.selectedNodeId,
    (newVal) => {
        nodeId.value = newVal;
        if (props.selectedNodeId !== null) {
            selectedTab.value = props.isTemporary ? 1 : 2;
        } else if (!openChatId.value) {
            selectedTab.value = 0;
        }
    },
);

watch(openChatId, (newVal) => {
    if (newVal) {
        selectedTab.value = props.isTemporary ? 1 : 2;
    } else if (props.selectedNodeId === null) {
        selectedTab.value = 0;
    }
});

onMounted(() => {
    const unsubscribeOpenNodeData = graphEvents.on('open-node-data', ({ selectedNodeId }) => {
        if (selectedNodeId) {
            nodeId.value = selectedNodeId;
            changeTab(props.isTemporary ? 1 : 2);
        }
    });

    onUnmounted(unsubscribeOpenNodeData);

    const unsubscribeOpenUpcomingNodeData = graphEvents.on('open-upcoming-node-data', () => {
        nodeId.value = null;
    });

    onUnmounted(unsubscribeOpenUpcomingNodeData);
});
</script>

<template>
    <div
        class="dark:bg-anthracite/75 bg-stone-gray/20 border-stone-gray/10 absolute top-2 right-2
            z-10 flex h-[calc(100%-1rem)] flex-col items-center justify-start rounded-2xl border-2
            px-4 py-8 shadow-lg backdrop-blur-md transition-[width] duration-200 ease-in-out"
        :class="{
            'w-[30rem]': isRightOpen,
            'w-[3rem]': !isRightOpen,
        }"
    >
        <HeadlessTabGroup
            as="div"
            class="flex h-full w-full flex-col items-center"
            :selected-index="selectedTab"
            @change="changeTab"
        >
            <HeadlessTabList
                class="mb-6 flex h-fit w-full flex-wrap justify-center space-x-2 duration-200"
                :class="{ 'pointer-events-none opacity-0': !isRightOpen }"
            >
                <UiGraphSidebarTab v-if="!isTemporary" name="Blocks" icon="ClarityBlockSolid" />
                <UiGraphSidebarTab name="Canvas" icon="MaterialSymbolsSettingsRounded" />
                <UiGraphSidebarTab name="Node Data" icon="MdiDatabaseOutline" />
            </HeadlessTabList>

            <HeadlessTabPanels
                class="relative h-[calc(100%-1rem-3.5rem)] w-full overflow-hidden duration-200"
                :class="{ 'pointer-events-none opacity-0': !isRightOpen }"
            >
                <Transition
                    v-if="!isTemporary"
                    enter-active-class="transition-opacity duration-200 ease-in-out"
                    enter-from-class="opacity-0"
                    leave-active-class="transition-opacity duration-200 ease-in-out absolute inset-0"
                    leave-to-class="opacity-0"
                >
                    <HeadlessTabPanel class="h-full w-full">
                        <UiGraphSidebarBlocks />
                    </HeadlessTabPanel>
                </Transition>
                <Transition
                    enter-active-class="transition-opacity duration-200 ease-in-out"
                    enter-from-class="opacity-0"
                    leave-active-class="transition-opacity duration-200 ease-in-out absolute inset-0"
                    leave-to-class="opacity-0"
                >
                    <HeadlessTabPanel class="h-full w-full">
                        <UiGraphSidebarCanvasConfig v-if="graph" :graph="graph" />
                    </HeadlessTabPanel>
                </Transition>
                <Transition
                    enter-active-class="transition-opacity duration-200 ease-in-out"
                    enter-from-class="opacity-0"
                    leave-active-class="transition-opacity duration-200 ease-in-out absolute inset-0"
                    leave-to-class="opacity-0"
                >
                    <HeadlessTabPanel class="h-full w-full">
                        <UiGraphSidebarNodeData
                            v-if="graph.id"
                            :node-id="nodeId"
                            :graph-id="graph.id"
                        />
                    </HeadlessTabPanel>
                </Transition>
            </HeadlessTabPanels>
        </HeadlessTabGroup>

        <div
            class="bg-anthracite hover:bg-obsidian border-stone-gray/10 absolute bottom-1/2 -left-3
                flex h-10 w-6 cursor-pointer items-center justify-center rounded-lg border-2
                transition duration-200 ease-in-out"
            role="button"
            @click="toggleRightSidebar"
        >
            <UiIcon
                name="TablerChevronCompactLeft"
                class="text-stone-gray h-6 w-6"
                :class="{
                    'rotate-180': isRightOpen,
                }"
            />
        </div>
    </div>
</template>

<style scoped></style>
