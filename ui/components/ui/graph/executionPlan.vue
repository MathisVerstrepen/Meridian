<script lang="ts" setup>
import type { ExecutionPlanResponse, ExecutionPlanStep } from '@/types/chat';
import { NodeTypeEnum } from '@/types/enums';
import { useVueFlow } from '@vue-flow/core';
import { motion } from 'motion-v';

const props = defineProps<{
    graphId: string;
}>();

// --- Stores ---
const canvasSaveStore = useCanvasSaveStore();

// --- Actions/Methods from Stores ---
const { saveGraph } = canvasSaveStore;

// --- Composables ---
const { fitView } = useVueFlow('main-graph-' + props.graphId);
const graphEvents = useGraphEvents();
const nodeRegistry = useNodeRegistry();
const { error, warning } = useToast();

// --- Local State ---
const plan = ref<ExecutionPlanResponse | null>(null);
const currentStep = ref(0);
// 0 = not started, 1 = in progress, 2 = done
const doneTable = ref<Record<string, number>>({});
const isExecuting = ref(false);
const pendingExecutions = ref<Set<string>>(new Set());
const isOpen = ref(false);
const startTime = ref(Date.now());
const selectedCategories = ref<Record<string, boolean>>({
    not_started: true,
    in_progress: true,
    done: true,
});

// --- Computed Properties ---
const progressRatio = computed(() => {
    if (!plan.value) return 0;
    return currentStep.value / plan.value.steps.length;
});

// --- Methods ---
const streamNode = async (nodeId: string) => {
    try {
        doneTable.value[nodeId] = 1;
        pendingExecutions.value.add(nodeId);

        await nodeRegistry.execute(nodeId);

        await saveGraph();
        await nextTick();

        doneTable.value[nodeId] = 2;
        pendingExecutions.value.delete(nodeId);
        currentStep.value++;
    } catch (err) {
        console.error(`Error executing node ${nodeId}:`, err);
        error(`Failed to execute node ${nodeId}`, {
            title: 'Execution Error',
        });
        doneTable.value[nodeId] = 0;
        pendingExecutions.value.delete(nodeId);
        throw err;
    }
};

const isStepReady = (step: ExecutionPlanStep) => {
    if (step.depends_on.length === 0) return true;
    return step.depends_on.every((dep) => doneTable.value[dep] === 2);
};

const executeStep = async (step: ExecutionPlanStep) => {
    if (isStepReady(step) && doneTable.value[step.node_id] === 0) {
        streamNode(step.node_id);
    }
};

const executer = async () => {
    if (!plan.value || isExecuting.value) return;

    isExecuting.value = true;
    currentStep.value = 0;
    doneTable.value = {};
    pendingExecutions.value.clear();
    startTime.value = Date.now();

    try {
        // Initialize all steps as not started
        for (const step of plan.value.steps) {
            doneTable.value[step.node_id] = 0;
        }

        // Execute initial ready steps
        for (const step of plan.value.steps) {
            await executeStep(step);
        }

        // Watch for changes and execute dependent steps
        const stopWatcher = watch(
            () => doneTable.value,
            async () => {
                if (!plan.value) return;

                const allDone = Object.values(doneTable.value).every((done) => done === 2);
                if (allDone && pendingExecutions.value.size === 0) {
                    stopWatcher();
                    isExecuting.value = false;
                    return;
                }

                // Execute any newly ready steps
                for (const step of plan.value.steps) {
                    executeStep(step);
                }
            },
            { deep: true },
        );
    } catch (err) {
        isExecuting.value = false;
        pendingExecutions.value.clear();
        console.error('Execution plan failed:', err);
        error('Execution plan failed', { title: 'Execution Error' });
        throw err;
    }
};

const stopExecution = async () => {
    isExecuting.value = false;
    plan.value = null;
    currentStep.value = 0;
    doneTable.value = {};

    // For each pending execution, we stop it
    let jobs: Promise<void>[] = [];
    for (const nodeId of pendingExecutions.value) {
        jobs.push(nodeRegistry.stop(nodeId));
    }
    await Promise.all(jobs);

    pendingExecutions.value.clear();
    warning('Execution stopped', { title: 'Execution Stopped' });
};

const focusToNode = (nodeId: string) => {
    fitView({
        nodes: [nodeId],
        duration: 1000,
        padding: 2,
    });
};

// --- Watchers ---
// When the execution end, we close the plan after a delay of 5 seconds
// if the plan is not open anymore, if it is open, we wait for it to be close
watch(
    () => isExecuting.value,
    (executing) => {
        if (!executing) {
            const closePlan = () => {
                setTimeout(() => {
                    if (!isExecuting.value && !isOpen.value) {
                        plan.value = null;
                        currentStep.value = 0;
                        doneTable.value = {};
                        pendingExecutions.value.clear();
                    }
                }, 5000);
            };

            if (isOpen.value) {
                const stopWatcher = watch(
                    () => isOpen.value,
                    (open) => {
                        if (!open) {
                            stopWatcher();
                            closePlan();
                        }
                    },
                    { immediate: true },
                );
            } else {
                closePlan();
            }
        }
    },
    { immediate: true },
);

// --- Lifecycle ---
onMounted(() => {
    const unsubscribe = graphEvents.on('execution-plan', async (data) => {
        plan.value = data.plan || null;
        if (plan.value) {
            currentStep.value = 0;
            doneTable.value = {};
            executer();
        }
    });

    onUnmounted(unsubscribe);
});
</script>

<template>
    <AnimatePresence>
        <motion.div
            v-if="plan && plan.steps.length > 0"
            key="execution-plan"
            :initial="{ opacity: 0, y: -50, width: '10%', height: '3rem' }"
            :animate="{
                opacity: 1,
                y: 0,
                width: '25%',
                height: isOpen ? '20rem' : '3rem',
                transition: {
                    y: { duration: 0.15 },
                    width: { delay: 0.05, duration: 0.2 },
                    height: { duration: 0.3, ease: 'easeInOut' },
                },
            }"
            :exit="{
                opacity: 0,
                y: -50,
                width: '10%',
                height: '3rem',
                transition: {
                    width: { duration: 0.2 },
                    y: { delay: 0.15, duration: 0.1 },
                    height: { duration: 0.3, ease: 'easeInOut' },
                },
            }"
            class="bg-anthracite/75 border-stone-gray/10 absolute top-2 left-1/2 z-10 flex h-12 w-[25%]
                -translate-x-1/2 flex-col rounded-2xl border-2 p-1 px-2 shadow-lg backdrop-blur-md"
        >
            <div class="flex h-9 w-full shrink-0 items-center justify-between gap-5">
                <div
                    class="text-soft-silk bg-soft-silk/10 rounded-lg px-2 py-0.5 text-sm font-bold"
                >
                    {{ currentStep }} / {{ plan?.steps.length }}
                </div>

                <UiGraphProgressBar :value="progressRatio" />

                <div>
                    <button
                        class="nodrag bg-soft-silk/10 hover:bg-soft-silk/20 dark:text-soft-silk text-anthracite relative flex h-8
                            w-8 flex-shrink-0 cursor-pointer items-center justify-center rounded-2xl transition-all duration-200
                            ease-in-out"
                        @click="stopExecution"
                        v-if="progressRatio < 1"
                    >
                        <UiIcon name="MaterialSymbolsStopRounded" class="h-5 w-5" />
                    </button>

                    <div
                        class="nodrag bg-olive-grove/40 text-soft-silk relative flex h-8 w-8 flex-shrink-0 cursor-pointer
                            items-center justify-center rounded-2xl"
                        v-else
                    >
                        <UiIcon name="MaterialSymbolsCheckSmallRounded" class="h-5 w-5" />
                    </div>
                </div>
            </div>

            <div class="my-2 flex items-center justify-between gap-2 px-2" v-if="isOpen">
                <NuxtTime
                    :datetime="startTime"
                    relative
                    class="text-soft-silk/50 text-xs font-bold"
                />

                <div class="flex items-center gap-2">
                    <button
                        class="bg-stone-gray/20 border-stone-gray/50 h-4 w-8 flex-shrink-0 cursor-pointer items-center
                            justify-center rounded-full border-2 transition-all duration-200 ease-in-out"
                        @click="selectedCategories.not_started = !selectedCategories.not_started"
                        :class="{
                            '!bg-stone-gray !border-transparent': selectedCategories.not_started,
                        }"
                        title="Toggle Not Started"
                    ></button>
                    <button
                        class="bg-slate-blue/20 border-slate-blue/50 h-4 w-8 flex-shrink-0 cursor-pointer items-center
                            justify-center rounded-full border-2 transition-all duration-200 ease-in-out"
                        @click="selectedCategories.in_progress = !selectedCategories.in_progress"
                        :class="{
                            '!bg-slate-blue !border-transparent': selectedCategories.in_progress,
                        }"
                        title="Toggle In Progress"
                    ></button>
                    <button
                        class="bg-olive-grove/20 border-olive-grove/50 h-4 w-8 flex-shrink-0 cursor-pointer items-center
                            justify-center rounded-full border-2 transition-all duration-200 ease-in-out"
                        @click="selectedCategories.done = !selectedCategories.done"
                        :class="{
                            '!bg-olive-grove !border-transparent': selectedCategories.done,
                        }"
                        title="Toggle Done"
                    ></button>
                </div>
            </div>

            <ul
                v-if="isOpen"
                class="hide-scrollbar mb-2 flex h-min w-full flex-wrap items-center justify-center gap-2 overflow-y-auto"
            >
                <li
                    v-for="step in plan?.steps"
                    :key="step.node_id"
                    class="bg-stone-gray/10 border-stone-gray/20 text-soft-silk relative flex h-10 w-[48%] items-center
                        justify-between overflow-hidden rounded-lg border-2 px-2 py-2 transition-all duration-200
                        ease-in-out"
                    :class="{
                        '!bg-olive-grove/20 !border-olive-grove/50': doneTable[step.node_id] === 2,
                        '!bg-slate-blue/20 !border-slate-blue/50': doneTable[step.node_id] === 1,
                    }"
                    v-show="
                        (selectedCategories.not_started && doneTable[step.node_id] === 0) ||
                        (selectedCategories.in_progress && doneTable[step.node_id] === 1) ||
                        (selectedCategories.done && doneTable[step.node_id] === 2)
                    "
                >
                    <span
                        class="hover:text-obsidian absolute top-0 left-0 h-2 w-8 rounded-tl-lg rounded-br-xl"
                        :class="{
                            'bg-terracotta-clay': step.node_type === NodeTypeEnum.PARALLELIZATION,
                            'bg-olive-grove': step.node_type === NodeTypeEnum.TEXT_TO_TEXT,
                            'bg-sunbaked-sand-dark': step.node_type === NodeTypeEnum.ROUTING,
                        }"
                    >
                    </span>
                    <span class="mx-2 text-[9px] font-bold"
                        >{{ step.node_id.slice(0, 24) }}...</span
                    >
                    <button
                        class="nodrag bg-stone-gray/10 hover:bg-stone-gray/20 dark:text-soft-silk text-anthracite relative flex h-6
                            w-6 flex-shrink-0 cursor-pointer items-center justify-center rounded-2xl transition-all duration-200
                            ease-in-out"
                        @click="focusToNode(step.node_id)"
                    >
                        <UiIcon name="LetsIconsTarget" class="h-4 w-4" />
                    </button>
                </li>
            </ul>

            <div
                class="bg-anthracite hover:bg-obsidian border-stone-gray/10 absolute -bottom-4 left-1/2 flex h-6 w-10
                    -translate-x-1/2 cursor-pointer items-center justify-center rounded-lg border-2 transition
                    duration-200 ease-in-out"
                @click="isOpen = !isOpen"
                role="button"
            >
                <UiIcon
                    name="TablerChevronCompactLeft"
                    class="text-stone-gray h-6 w-6 -rotate-90 transition-transform duration-200 ease-in-out"
                    :class="{
                        'rotate-90': isOpen,
                    }"
                />
            </div>
        </motion.div>
    </AnimatePresence>
</template>

<style scoped></style>
