<script lang="ts" setup>
import type { ExecutionPlanResponse, ExecutionPlanStep } from '@/types/chat';

// --- Stores ---
const canvasSaveStore = useCanvasSaveStore();

// --- Actions/Methods from Stores ---
const { saveGraph } = canvasSaveStore;

// --- Composables ---
const graphEvents = useGraphEvents();
const nodeRegistry = useNodeRegistry();
const { error } = useToast();

// --- Local State ---
const plan = ref<ExecutionPlanResponse | null>(null);
const currentStep = ref(0);
// 0 = not started, 1 = in progress, 2 = done
const doneTable = ref<Record<string, number>>({});
const isExecuting = ref(false);
const pendingExecutions = ref<Set<string>>(new Set());

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

const stopExecution = () => {
    // TODO: Implement cancellation logic
    isExecuting.value = false;
    pendingExecutions.value.clear();
};

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
    <div
        class="bg-anthracite/75 border-stone-gray/10 absolute top-2 left-1/2 z-10 flex h-12 w-[25%]
            -translate-x-1/2 items-center justify-between gap-5 rounded-2xl border-2 p-1 px-2 shadow-lg
            backdrop-blur-md"
        v-show="plan"
    >
        <div class="text-soft-silk bg-soft-silk/10 rounded-lg px-2 py-0.5 text-sm font-bold">
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
</template>

<style scoped></style>
