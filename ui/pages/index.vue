<script lang="ts" setup>
import { DEFAULT_NODE_ID } from '@/constants';
import { NodeTypeEnum, MessageRoleEnum, MessageContentTypeEnum } from '@/types/enums';
import type { Graph, MessageContent } from '@/types/graph';
import type { File } from '@/types/files';
import type { User } from '@/types/user';

// --- Page Meta ---
definePageMeta({ layout: 'blank', middleware: 'auth' });
useHead({
    title: 'Meridian - Home',
});

// --- Stores ---
const chatStore = useChatStore();
const globalSettingsStore = useSettingsStore();

// --- State from Stores (Reactive Refs) ---
const { openChatId, currentModel } = storeToRefs(chatStore);
const { modelsSettings } = storeToRefs(globalSettingsStore);

// --- Actions/Methods from Stores ---
const { resetChatState, addMessage } = chatStore;

// --- Composables ---
const { fileToMessageContent } = useFiles();
const { getGraphs, createGraph } = useAPI();
const { generateId } = useUniqueId();
const { user } = useUserSession();

// --- Local State ---
const graphs = ref<Graph[]>([]);
const isLoading = ref(true);

// --- Core Logic Functions ---
const fetchGraphs = async () => {
    try {
        const response = await getGraphs();
        graphs.value = response;
    } catch (error) {
        console.error('Error fetching graphs:', error);
    } finally {
        isLoading.value = false;
    }
};

const openNewFromInput = async (message: string, files: File[]) => {
    const newGraph = await createGraph();
    if (!newGraph) {
        console.error('Error creating new graph');
        return;
    }

    graphs.value.unshift(newGraph);
    currentModel.value = modelsSettings.value.defaultModel;

    const textToTextNodeId = generateId();
    openChatId.value = textToTextNodeId;

    let filesContent: MessageContent[] = [];
    if (files && files.length > 0) {
        filesContent = files.map((file) => fileToMessageContent(file));
    }

    addMessage(
        {
            role: MessageRoleEnum.user,
            content: [
                {
                    type: MessageContentTypeEnum.TEXT,
                    text: message,
                },
                ...filesContent,
            ],
            model: currentModel.value,
            node_id: textToTextNodeId,
            type: NodeTypeEnum.TEXT_TO_TEXT,
            data: {
                reply: '',
                model: currentModel.value,
                files: files,
            },
            usageData: null,
        },
        textToTextNodeId,
    );

    navigateTo(`graph/${newGraph.id}?startStream=true&fromHome=true`);
};

const openNewFromButton = async (wanted: 'canvas' | 'chat') => {
    const newGraph = await createGraph();
    if (!newGraph) {
        console.error('Error creating new graph');
        return;
    }

    graphs.value.unshift(newGraph);
    currentModel.value = modelsSettings.value.defaultModel;

    resetChatState();
    openChatId.value = wanted === 'chat' ? DEFAULT_NODE_ID : null;
    navigateTo(`graph/${newGraph.id}?fromHome=true`);
};

// --- Lifecycle Hooks ---
onMounted(() => {
    nextTick(() => {
        resetChatState();
        fetchGraphs();
    });
});
</script>

<template>
    <div class="bg-anthracite relative h-full w-full">
        <!-- Background dots -->
        <svg class="absolute top-0 left-0 z-0 h-full w-full">
            <pattern id="home-pattern" patternUnits="userSpaceOnUse" width="25" height="25">
                <circle cx="12.5" cy="12.5" r="1" fill="var(--color-stone-gray)" />
            </pattern>

            <rect width="100%" height="100%" :fill="`url(#home-pattern)`" />
        </svg>

        <!-- Background gradient over dots -->
        <div
            class="from-anthracite/100 to-anthracite/0 absolute top-0 left-0 z-10 h-full w-full"
            style="
                background: radial-gradient(
                    ellipse 100% 70% at 50% 30%,
                    var(--color-anthracite) 0%,
                    transparent 100%
                );
            "
        ></div>

        <!-- Main content -->
        <div class="relative z-20 flex h-[60%] w-full flex-col items-center justify-center">
            <h1 class="font-outfit text-soft-silk mb-16 text-5xl font-bold">
                <span class="text-terracotta-clay">Hello World !</span> What can I do for you ?
            </h1>

            <UiChatTextInput
                :isLockedToBottom="true"
                @trigger-scroll="() => {}"
                @generate="openNewFromInput"
                class="max-h-[300px]"
            ></UiChatTextInput>

            <p class="font-outfit text-soft-silk/50 my-5 font-bold">OR</p>

            <div class="flex w-full justify-center gap-4">
                <!-- New canvas button -->
                <button
                    class="bg-terracotta-clay/10 border-terracotta-clay-dark/50 hover:bg-terracotta-clay/20 flex cursor-pointer
                        items-center gap-2 rounded-3xl border-2 px-10 py-4 backdrop-blur transition duration-200 ease-in-out"
                    @click="openNewFromButton('canvas')"
                >
                    <UiIcon name="Fa6SolidPlus" class="text-soft-silk h-6 w-6 opacity-80" />
                    <span class="text-soft-silk/80 text-lg font-bold">Create new canvas</span>
                </button>

                <!-- New chat button -->
                <button
                    class="bg-obsidian/20 border-obsidian/50 hover:bg-obsidian/40 flex cursor-pointer items-center gap-2
                        rounded-3xl border-2 px-10 py-4 backdrop-blur transition duration-200 ease-in-out"
                    @click="openNewFromButton('chat')"
                >
                    <UiIcon
                        name="MaterialSymbolsAndroidChat"
                        class="text-soft-silk h-6 w-6 opacity-80"
                    />
                    <span class="text-soft-silk/80 text-lg font-bold">Open new chat</span>
                </button>
            </div>
        </div>

        <!-- Recent canvas section -->
        <div
            class="bg-obsidian/50 relative z-20 mx-auto flex h-[40%] w-[98%] flex-col items-center rounded-t-3xl p-8
                backdrop-blur"
        >
            <h2 class="font-outfit text-stone-gray mb-8 text-xl font-bold">Recent Canvas</h2>
            <div
                class="grid h-full w-full auto-rows-[9rem] grid-cols-4 gap-5 overflow-y-auto"
                v-if="!isLoading && graphs.length > 0"
            >
                <NuxtLink
                    v-for="graph in graphs"
                    :key="graph.id"
                    class="bg-obsidian/70 hover:bg-obsidian border-obsidian flex h-36 w-full cursor-pointer flex-col
                        items-start justify-center gap-5 rounded-2xl border-2 p-6 transition-colors duration-200 ease-in-out"
                    role="button"
                    :to="{ name: 'graph-id', params: { id: graph.id } }"
                >
                    <div class="text-stone-gray flex gap-3">
                        <UiIcon name="MaterialSymbolsFlowchartSharp" class="h-7 w-7" />
                        <span class="text-lg font-bold">
                            {{ graph.name }}
                        </span>
                    </div>

                    <div class="flex w-full items-center justify-between text-sm">
                        <div
                            class="bg-terracotta-clay-dark/25 text-terracotta-clay rounded-lg px-3 py-1 font-bold"
                        >
                            {{ graph.node_count }} nodes
                        </div>

                        <NuxtTime
                            class="text-stone-gray"
                            :datetime="new Date(graph.updated_at)"
                            locale="en-US"
                            relative
                        />
                    </div>
                </NuxtLink>
            </div>

            <!-- If no canvas saved -->
            <div
                v-if="!isLoading && graphs.length === 0"
                class="flex h-full w-full items-center justify-center"
            >
                <span class="text-soft-silk/50"> No recent canvas found. Create a new one ! </span>
            </div>

            <!-- Loading state -->
            <div
                v-if="isLoading"
                class="flex h-full w-full flex-col items-center justify-center gap-4 opacity-50"
            >
                <div
                    class="border-soft-silk h-8 w-8 animate-spin rounded-full border-4 border-t-transparent"
                ></div>
                <span class="text-soft-silk">Loading canvas...</span>
            </div>
        </div>

        <!-- User avatar and settings link -->
        <div
            class="bg-obsidian/50 absolute top-8 right-8 z-30 flex items-center gap-4 rounded-full p-2 pr-2
                backdrop-blur"
        >
            <img
                :src="(user as User).avatarUrl"
                :srcset="(user as User).avatarUrl"
                class="bg-obsidian h-10 w-10 rounded-full object-cover"
                loading="lazy"
                :width="40"
                :height="40"
                v-if="(user as User).avatarUrl"
            />
            <span v-else class="text-stone-gray font-bold">
                <UiIcon name="MaterialSymbolsAccountCircle" class="h-10 w-10" />
            </span>
            <span class="text-stone-gray font-bold">{{ (user as User).name }}</span>

            <NuxtLink
                to="/settings"
                class="text-stone-gray hover:bg-stone-gray/10 ml-2 flex h-10 w-10 items-center justify-center rounded-full
                    transition-all duration-200 hover:cursor-pointer"
                aria-label="Settings"
            >
                <UiIcon name="MaterialSymbolsSettingsRounded" class="h-6 w-6" />
            </NuxtLink>
        </div>
    </div>
</template>

<style scoped></style>
