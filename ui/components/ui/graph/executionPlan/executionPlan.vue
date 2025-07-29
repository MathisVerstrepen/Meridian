<script lang="ts" setup>
import type { ExecutionPlanResponse, ExecutionPlanStep } from '@/types/chat';
import { motion } from 'motion-v';

const props = defineProps<{
    graphId: string;
}>();

// --- Stores ---
const canvasSaveStore = useCanvasSaveStore();

// --- Actions/Methods from Stores ---
const { saveGraph } = canvasSaveStore;

// --- Composables ---
const graphEvents = useGraphEvents();
const nodeRegistry = useNodeRegistry();
const { error, warning } = useToast();
const { toggleEdgeAnimation } = useGraphActions();

// --- Local State ---
const closeTimerId = ref<ReturnType<typeof setTimeout> | null>(null);
const plan = ref<ExecutionPlanResponse | null>(null);
const currentStep = ref(0);
// 0 = not started, 1 = in progress, 2 = done
const doneTable = ref<Record<string, number>>({});
const pendingExecutions = ref<Set<string>>(new Set());
const startTime = ref(Date.now());
const isExecuting = ref(false);
const isClosing = ref(false);
const isOpen = ref(false);
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
        toggleEdgeAnimation(props.graphId, false, null, nodeId);
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
            for (const dep of step.depends_on) {
                toggleEdgeAnimation(props.graphId, true, dep, step.node_id);
            }
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

const clearPlanData = () => {
    plan.value = null;
    currentStep.value = 0;
    doneTable.value = {};
    pendingExecutions.value.clear();
    isClosing.value = false;
    if (closeTimerId.value) {
        clearTimeout(closeTimerId.value);
        closeTimerId.value = null;
    }
};

const schedulePlanClosure = () => {
    if (closeTimerId.value) clearTimeout(closeTimerId.value);
    isClosing.value = true;
    closeTimerId.value = setTimeout(() => {
        clearPlanData();
    }, 5000);
};

const cancelPlanClosure = () => {
    if (closeTimerId.value) {
        clearTimeout(closeTimerId.value);
        closeTimerId.value = null;
    }
    isClosing.value = false;
};

// --- Watchers ---
// When the execution end, we close the plan after a delay of 5 seconds
// if the plan is not open anymore, if it is open, we wait for it to be close
watch(isExecuting, (executing) => {
    // When execution finishes, schedule the plan to close if the panel is not open.
    if (!executing && plan.value && !isOpen.value) {
        schedulePlanClosure();
    }
});

watch(isOpen, (open) => {
    // Only act if execution is already finished.
    const executionFinished = !isExecuting.value && plan.value !== null;
    if (!executionFinished) return;

    if (open) {
        // If the panel is opened, cancel any scheduled closure.
        cancelPlanClosure();
    } else {
        // If the panel is closed after being open, schedule the closure.
        schedulePlanClosure();
    }
});

// --- Lifecycle ---
onMounted(() => {
    const unsubscribe = graphEvents.on('execution-plan', async (data) => {
        plan.value = data.plan || null;
        if (plan.value) {
            // Cancel any pending closure from a previous run. This prevents
            // a lingering timer from clearing the new, active plan.
            cancelPlanClosure();

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
            :initial="{ opacity: 0, y: -50, width: '40%', height: '3rem' }"
            :animate="{
                opacity: 1,
                y: 0,
                width: '100%',
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
                width: '40%',
                height: '3rem',
                transition: {
                    width: { duration: 0.2 },
                    y: { delay: 0.15, duration: 0.1 },
                    height: { duration: 0.3, ease: 'easeInOut' },
                },
            }"
            class="bg-anthracite/75 border-stone-gray/10 flex h-12 w-full flex-col rounded-2xl border-2 p-1 px-2
                shadow-lg backdrop-blur-md"
        >
            <div class="flex h-9 w-full shrink-0 items-center justify-between gap-5">
                <div
                    class="text-soft-silk bg-soft-silk/10 rounded-lg px-2 py-0.5 text-sm font-bold"
                >
                    {{ currentStep }} / {{ plan?.steps.length }}
                </div>

                <UiGraphExecutionPlanProgressBar :value="progressRatio" />

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
                            items-center justify-center overflow-hidden rounded-2xl"
                        v-else
                    >
                        <UiIcon
                            name="MaterialSymbolsCheckSmallRounded"
                            class="relative z-10 h-5 w-5"
                        />
                        <div v-if="isClosing" class="clock-loader absolute inset-0 z-0"></div>
                    </div>
                </div>
            </div>

            <UiGraphExecutionPlanHeader
                v-if="isOpen"
                :startTime="startTime"
                :selectedCategories="selectedCategories"
            />

            <UiGraphExecutionPlanActivityList
                v-if="isOpen"
                :plan="plan"
                :doneTable="doneTable"
                :selectedCategories="selectedCategories"
                :graphId="graphId"
            />

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

<style scoped>
@property --progress-angle {
    syntax: '<angle>';
    inherits: false;
    initial-value: 0deg;
}

.clock-loader {
    --progress-angle: 0deg;
    background: conic-gradient(
        color-mix(in oklab, var(--color-olive-grove) 50%, transparent) var(--progress-angle),
        transparent var(--progress-angle)
    );
    animation: fill-clock 5s linear forwards;
}

@keyframes fill-clock {
    to {
        --progress-angle: 360deg;
    }
}
</style>
