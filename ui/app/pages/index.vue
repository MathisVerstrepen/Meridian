<script lang="ts" setup>
import { DEFAULT_NODE_ID } from '@/constants';
import { NodeTypeEnum, MessageRoleEnum, MessageContentTypeEnum } from '@/types/enums';
import type { Graph, Folder, Workspace, MessageContent, BlockDefinition } from '@/types/graph';
import type { User } from '@/types/user';
import type HomeRecentCanvasSection from '~/components/ui/home/recentCanvasSection.vue';
import { PLAN_LIMITS } from '@/constants/limits';

import { useSpring } from 'motion-v';

// --- Page Meta ---
definePageMeta({ layout: 'blank', middleware: 'auth' });
useHead({
    title: 'Meridian - Home',
});

// --- Stores ---
const chatStore = useChatStore();
const globalSettingsStore = useSettingsStore();

// --- State from Stores (Reactive Refs) ---
const { openChatId, upcomingModelData } = storeToRefs(chatStore);
const { modelsSettings, accountSettings, isReady } = storeToRefs(globalSettingsStore);

// --- Actions/Methods from Stores ---
const { resetChatState, addMessage } = chatStore;

// --- Local State ---
const graphs = ref<Graph[]>([]);
const folders = ref<Folder[]>([]);
const workspaces = ref<Workspace[]>([]);
const isLoading = ref(true);
const animWords = ref(Array(10).fill(false));
const pageRef = ref<HTMLElement | null>(null);
const recentCanvasComponentRef = ref<InstanceType<typeof HomeRecentCanvasSection> | null>(null);
const selectedNodeType = ref<BlockDefinition | null>(null);
const showWelcomeModal = ref(false);

// Motion state for scroll animation
const recentCanvasHeight = useSpring(40, { stiffness: 200, damping: 30 });
const mainContentHeight = useSpring(60, { stiffness: 200, damping: 30 });
const mainContentOpacity = useSpring(1, { stiffness: 200, damping: 30 });

const recentCanvasStyle = reactive({ height: '40%' });
const mainContentStyle = reactive({ height: '60%', opacity: 1 });

recentCanvasHeight.on('change', (v) => (recentCanvasStyle.height = `${v}%`));
mainContentHeight.on('change', (v) => (mainContentStyle.height = `${v}%`));
mainContentOpacity.on('change', (v) => (mainContentStyle.opacity = v));

// --- Composables ---
const { fileToMessageContent } = useFiles();
const { getGraphs, getHistoryFolders, getWorkspaces, createGraph } = useAPI();
const { generateId } = useUniqueId();
const { user, fetch: fetchUserSession } = useUserSession();
const { error } = useToast();
const { handleDeleteGraph } = useGraphDeletion(graphs, undefined);

// --- Core Logic Functions ---

const handleWheel = (event: WheelEvent) => {
    // Workspace Switching (Shift + Wheel)
    if (event.shiftKey) {
        recentCanvasComponentRef.value?.handleWorkspaceWheel(event);
        return;
    }

    const currentHeight = recentCanvasHeight.get();
    const isScrollingDown = event.deltaY > 0;
    const isScrollingUp = event.deltaY < 0;

    // Access the scroll container exposed by the child component
    const innerScrollEl = recentCanvasComponentRef.value?.scrollContainer;

    if (!innerScrollEl) return;

    // When scrolling down, expand the container.
    if (isScrollingDown && currentHeight < 90) {
        recentCanvasHeight.set(90);
        mainContentHeight.set(10);
        mainContentOpacity.set(0);
    }
    // When scrolling up at the top of the inner scroll, collapse the container.
    else if (isScrollingUp && innerScrollEl.scrollTop === 0) {
        if (currentHeight > 40) {
            recentCanvasHeight.set(40);
            mainContentHeight.set(60);
            mainContentOpacity.set(1);
        }
    }
};

const fetchData = async () => {
    try {
        const [graphsData, foldersData, workspacesData] = await Promise.all([
            getGraphs(),
            getHistoryFolders(),
            getWorkspaces(),
        ]);
        graphs.value = graphsData;
        folders.value = foldersData;
        workspaces.value = workspacesData;
    } catch (err) {
        console.error('Error fetching data:', err);
        error('Failed to load history. Please try again.', { title: 'Load Error' });
    } finally {
        isLoading.value = false;
    }
};

const openNewFromInput = async (message: string, files: FileSystemObject[]) => {
    if ((user.value as User)?.plan_type === 'free') {
        const nonTemporaryGraphs = graphs.value.filter((g) => !g.temporary);
        if (nonTemporaryGraphs.length >= PLAN_LIMITS.FREE.MAX_GRAPHS) {
            error('You have reached the maximum number of canvases for the Free plan.', {
                title: 'Limit Reached',
            });
            return;
        }
    }

    const newGraph = await createGraph(false);
    if (!newGraph) {
        console.error('Error creating new graph');
        error('Failed to create new canvas. Please try again.', { title: 'Create Error' });
        return;
    }

    graphs.value.unshift(newGraph);
    upcomingModelData.value.data.model = modelsSettings.value.defaultModel;

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
            model: upcomingModelData.value.data.model as string,
            node_id: textToTextNodeId,
            type: selectedNodeType.value?.nodeType || NodeTypeEnum.TEXT_TO_TEXT,
            data: {
                reply: '',
                model: upcomingModelData.value.data.model as string,
                files: files,
            },
            usageData: null,
        },
        textToTextNodeId,
    );

    navigateTo(`graph/${newGraph.id}?startStream=true&fromHome=true`);
};

const openNewFromButton = async (wanted: 'canvas' | 'chat' | 'temporary') => {
    if (wanted !== 'temporary' && (user.value as User)?.plan_type === 'free') {
        const nonTemporaryGraphs = graphs.value.filter((g) => !g.temporary);
        if (nonTemporaryGraphs.length >= PLAN_LIMITS.FREE.MAX_GRAPHS) {
            error('You have reached the maximum number of canvases for the Free plan.', {
                title: 'Limit Reached',
            });
            return;
        }
    }

    const newGraph = await createGraph(wanted === 'temporary');
    if (!newGraph) {
        console.error('Error creating new graph');
        error('Failed to create new canvas. Please try again.', { title: 'Create Error' });
        return;
    }

    graphs.value.unshift(newGraph);
    upcomingModelData.value.data.model = modelsSettings.value.defaultModel;

    resetChatState();
    openChatId.value = wanted === 'chat' || wanted === 'temporary' ? DEFAULT_NODE_ID : null;
    navigateTo(`graph/${newGraph.id}?fromHome=true&temporary=${wanted === 'temporary'}`);
};

const handleWelcomeClose = async () => {
    showWelcomeModal.value = false;
    try {
        await $fetch('/api/auth/ack-welcome', { method: 'POST' });
        await fetchUserSession();
    } catch (err) {
        console.error('Failed to acknowledge welcome:', err);
    }
};

const handleWelcomeConfigure = async () => {
    await handleWelcomeClose();
    navigateTo('/settings?tab=account');
};

// --- Lifecycle Hooks ---
let animationTimeouts: Array<ReturnType<typeof setTimeout>> = [];

watch(
    isReady,
    (newVal) => {
        if (
            newVal &&
            user.value &&
            !(user.value as User).has_seen_welcome &&
            !accountSettings.value.openRouterApiKey
        ) {
            showWelcomeModal.value = true;
        }
    },
    { immediate: true },
);

onMounted(() => {
    nextTick(() => {
        // Text Animation on page load
        animationTimeouts.forEach((timeout) => clearTimeout(timeout));
        animationTimeouts = [];
        animWords.value = animWords.value.map(() => false);

        animWords.value.forEach((_, i) => {
            const timeout = setTimeout(() => {
                animWords.value[i] = true;
            }, i * 125);
            animationTimeouts.push(timeout);
        });

        // Fetch graphs and folders
        resetChatState();
        fetchData();

        // Add wheel listener for scroll animation
        const el = pageRef.value;
        if (el) {
            el.addEventListener('wheel', handleWheel, { passive: true });
        }
    });
});

onBeforeUnmount(() => {
    animationTimeouts.forEach((timeout) => clearTimeout(timeout));
    animationTimeouts = [];

    const el = pageRef.value;
    if (el) {
        el.removeEventListener('wheel', handleWheel);
    }
});
</script>

<template>
    <div ref="pageRef" class="bg-obsidian relative h-full w-full overflow-hidden">
        <UiSettingsUtilsBlobBackground />

        <div class="text-stone-gray/25 absolute top-4 left-4 text-sm">
            <span>Version {{ $nuxt.$config.public.version }}</span>
        </div>

        <!-- Background dots -->
        <svg class="absolute top-0 left-0 z-0 h-full w-full opacity-20">
            <pattern id="home-pattern" patternUnits="userSpaceOnUse" width="25" height="25">
                <circle cx="12.5" cy="12.5" r="1" fill="var(--color-soft-silk)" />
            </pattern>
            <rect width="100%" height="100%" :fill="`url(#home-pattern)`" />
        </svg>

        <!-- Main content -->
        <div
            :style="mainContentStyle"
            class="relative z-20 flex w-full flex-col items-center justify-center"
        >
            <!-- Text Animation on page load -->
            <h1 class="font-outfit text-soft-silk mb-16 text-5xl font-bold">
                <template
                    v-for="(word, i) in [
                        ['Hello', 'text-ember-glow/70'],
                        [' World', 'text-ember-glow/70'],
                        [' !', 'text-ember-glow/70'],
                        [' What'],
                        [' can'],
                        [' do'],
                        [' for'],
                        [' you'],
                        [' ?'],
                    ]"
                    :key="i"
                >
                    <span
                        :class="[
                            animWords[i] ? 'opacity-100' : 'opacity-0',
                            'duration-500',
                            word[1] || '',
                        ]"
                        >{{ word[0] }}</span
                    >
                </template>
            </h1>

            <UiChatTextInput
                :is-locked-to-bottom="true"
                :is-streaming="false"
                :node-type="NodeTypeEnum.TEXT_TO_TEXT"
                from="home"
                class="max-h-[300px]"
                @trigger-scroll="() => {}"
                @generate="openNewFromInput"
                @select-node-type="
                    (newType) => {
                        selectedNodeType = newType;
                    }
                "
            />

            <p class="font-outfit text-soft-silk/50 my-5 font-bold">OR</p>

            <div class="flex w-full justify-center gap-4">
                <!-- New canvas button -->
                <button
                    class="bg-ember-glow/10 border-ember-glow/30 hover:bg-ember-glow/20 flex
                        cursor-pointer items-center gap-2 rounded-3xl border-2 px-10 py-4
                        backdrop-blur-sm transition duration-200 ease-in-out"
                    @click="openNewFromButton('canvas')"
                >
                    <UiIcon name="Fa6SolidPlus" class="text-ember-glow/70 h-6 w-6 opacity-80" />
                    <span class="text-ember-glow/70 text-lg font-bold">Create new canvas</span>
                </button>

                <!-- New chat button -->
                <button
                    class="bg-stone-gray/10 border-stone-gray/20 hover:bg-stone-gray/20 flex
                        cursor-pointer items-center gap-2 rounded-3xl border-2 px-10 py-4
                        backdrop-blur-sm transition duration-200 ease-in-out"
                    @click="openNewFromButton('chat')"
                >
                    <UiIcon
                        name="MaterialSymbolsAndroidChat"
                        class="text-soft-silk h-6 w-6 opacity-80"
                    />
                    <span class="text-soft-silk/80 text-lg font-bold">Open new chat</span>
                </button>

                <button
                    class="bg-stone-gray/10 border-stone-gray/20 hover:bg-stone-gray/20 flex
                        cursor-pointer items-center gap-2 rounded-3xl border-2 border-dashed px-10
                        py-4 backdrop-blur-sm transition duration-200 ease-in-out"
                    @click="openNewFromButton('temporary')"
                >
                    <UiIcon
                        name="LucideMessageCircleDashed"
                        class="text-soft-silk h-6 w-6 opacity-80"
                    />
                    <span class="text-soft-silk/80 text-lg font-bold">Temporary chat</span>
                </button>
            </div>
        </div>

        <!-- Recent canvas section -->
        <div
            :style="recentCanvasStyle"
            class="bg-anthracite/20 border-stone-gray/10 absolute right-0 bottom-0 left-0 z-20
                mx-auto flex w-[98%] flex-col items-center rounded-t-3xl border-t-2 p-8 pb-0
                backdrop-blur-lg"
        >
            <UiHomeRecentCanvasSection
                ref="recentCanvasComponentRef"
                :graphs="graphs"
                :folders="folders"
                :workspaces="workspaces"
                :is-loading="isLoading"
                @delete="(id, name) => handleDeleteGraph(id, name, false)"
            />
        </div>

        <!-- User avatar and settings link -->
        <div
            class="bg-anthracite/20 border-stone-gray/10 text-soft-silk/80 absolute top-8 right-8
                z-30 flex min-w-56 items-center gap-5 rounded-full border p-2 pr-2 backdrop-blur-lg"
        >
            <NuxtLink
                class="flex min-h-10 w-fit min-w-0 cursor-pointer items-center gap-3 rounded-lg"
                to="/settings?tab=account"
            >
                <UiUtilsUserProfilePicture />
                <div class="flex grow items-center gap-2 overflow-hidden">
                    <span class="font-bold">{{ (user as User).name }}</span>
                    <UiUtilsPlanLevelChip :level="(user as User).plan_type" />
                </div>
            </NuxtLink>

            <NuxtLink
                to="/settings"
                class="hover:bg-stone-gray/10 ml-auto flex h-10 w-10 items-center justify-center
                    rounded-full transition-all duration-200 hover:cursor-pointer"
                aria-label="Settings"
            >
                <UiIcon name="MaterialSymbolsSettingsRounded" class="h-6 w-6" />
            </NuxtLink>
        </div>

        <!-- File prompt mountpoint -->
        <UiGraphNodeUtilsFilePromptMountpoint />

        <!-- Welcome Modal -->
        <UiHomeWelcomeModal
            :model-value="showWelcomeModal"
            @close="handleWelcomeClose"
            @configure="handleWelcomeConfigure"
        />
    </div>
</template>

<style scoped></style>
