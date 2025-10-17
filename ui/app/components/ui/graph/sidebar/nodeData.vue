<script lang="ts" setup>
import { useVueFlow, type Node } from '@vue-flow/core';
import { NodeTypeEnum, SavingStatus } from '@/types/enums';

const props = defineProps<{
    nodeId: string | null;
    graphId: string | null;
}>();

// --- Stores ---
const canvasSaveStore = useCanvasSaveStore();
const chatStore = useChatStore();

// --- Actions/Methods from Stores ---
const { setNeedSave } = canvasSaveStore;

// --- State from Stores (Reactive Refs) ---
const { currentModel } = storeToRefs(chatStore);

// --- Composables ---
const { getNodes } = useVueFlow('main-graph-' + props.graphId);
const { generateId } = useUniqueId();

// --- Local State ---
const node = ref<Node | null>(null);

// --- Core logic ---
const setNodeDataKey = (key: string, value: unknown) => {
    if (!node.value) return;

    const keys = key.split('.');
    let current = node.value.data || {};

    for (let i = 0; i < keys.length - 1; i++) {
        const part = keys[i];
        if (!current[part] || typeof current[part] !== 'object') {
            current[part] = {};
        }
        current = current[part];
    }

    current[keys[keys.length - 1]] = value;

    // Trigger reactivity
    node.value.data = { ...node.value.data };

    setNeedSave(SavingStatus.NOT_SAVED);
};

// --- Methods for Parallelization Node ---
const addParallelModel = () => {
    if (!node.value || node.value.type !== NodeTypeEnum.PARALLELIZATION) return;

    const newModel = {
        model: node.value.data.defaultModel,
        reply: '',
        id: generateId(),
    };
    const updatedModels = [...node.value.data.models, newModel];
    setNodeDataKey('models', updatedModels);
};

const removeParallelModel = (index: number) => {
    if (!node.value || node.value.type !== NodeTypeEnum.PARALLELIZATION) return;

    const updatedModels = [...node.value.data.models];
    updatedModels.splice(index, 1);
    setNodeDataKey('models', updatedModels);
};

// --- Watchers ---
watch(
    () => props.nodeId,
    (newVal) => {
        if (newVal) {
            node.value = getNodes.value.find((n) => n.id === newVal) || null;
        } else {
            node.value = null;
        }
    },
    { immediate: true },
);
</script>

<template>
    <div class="h-full w-full px-4">
        <Transition name="fade" mode="out-in">
            <div v-if="node" class="flex h-full flex-col space-y-6">
                <!-- Metadata Section -->
                <div class="flex flex-col space-y-2">
                    <h2
                        class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-1 text-sm font-bold"
                    >
                        Metadata
                    </h2>
                    <div class="flex flex-col gap-1 px-2">
                        <p class="text-stone-gray truncate text-xs">ID: {{ node.id }}</p>
                        <p class="text-stone-gray text-xs">Type: {{ node.type }}</p>
                    </div>
                </div>

                <!-- Prompt Node Settings -->
                <template v-if="node.type === NodeTypeEnum.PROMPT">
                    <div class="flex min-h-0 flex-1 flex-col space-y-2">
                        <h3
                            class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-1 text-sm
                                font-bold"
                        >
                            Original Prompt
                        </h3>
                        <UiGraphNodeUtilsTextarea
                            class="grow"
                            :reply="node.data.prompt"
                            :readonly="false"
                            color="grey"
                            placeholder="Enter your prompt here"
                            :autoscroll="false"
                            :parse-error="false"
                            @update:reply="(value: string) => setNodeDataKey('prompt', value)"
                        />
                    </div>
                </template>

                <!-- Text to Text Node Settings -->
                <template v-else-if="node.type === NodeTypeEnum.TEXT_TO_TEXT">
                    <div class="flex flex-col space-y-2">
                        <h3
                            class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-1 text-sm
                                font-bold"
                        >
                            Model
                        </h3>
                        <UiModelsSelect
                            :model="node.data.model"
                            :set-model="
                                (model: string) => {
                                    currentModel = model;
                                    setNodeDataKey('model', model);
                                }
                            "
                            :disabled="false"
                            to="right"
                            variant="grey"
                            teleport
                        />
                    </div>

                    <div class="flex flex-col space-y-2">
                        <h3
                            class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-1 text-sm
                                font-bold"
                        >
                            Tools
                        </h3>
                        <div class="flex flex-wrap gap-2 px-1">
                            <button
                                class="group relative flex h-16 w-32 cursor-pointer flex-col
                                    items-center justify-center gap-1 rounded-lg p-2 text-center
                                    text-sm font-bold ring-2 transition-all duration-200
                                    ease-in-out"
                                title="Enable or disable web search for this node."
                                :class="[
                                    node.data.isWebSearch
                                        ? 'bg-ember-glow/10 ring-ember-glow text-ember-glow'
                                        : `bg-stone-gray/10 hover:bg-stone-gray/20 text-soft-silk/80
                                            hover:text-soft-silk/90 ring-stone-gray/20
                                            hover:ring-stone-gray/40`,
                                ]"
                                @click="setNodeDataKey('isWebSearch', !node.data.isWebSearch)"
                            >
                                <UiIcon name="MdiWeb" class="h-5 w-5" />
                                Web Search
                            </button>
                        </div>
                    </div>
                </template>

                <!-- Parallelization Node Settings -->
                <template v-else-if="node.type === NodeTypeEnum.PARALLELIZATION">
                    <div class="flex flex-col space-y-2">
                        <h3
                            class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-1 text-sm
                                font-bold"
                        >
                            Parallel Models
                        </h3>
                        <div class="flex flex-col gap-2">
                            <div
                                v-for="(model, index) in node.data.models"
                                :key="model.id"
                                class="flex w-full items-center gap-2"
                            >
                                <span class="text-stone-gray font-mono text-xs"
                                    >#{{ index + 1 }}</span
                                >
                                <UiModelsSelect
                                    :model="model.model"
                                    :set-model="
                                        (newModel: string) => {
                                            const updatedModels = [...node.data.models];
                                            updatedModels[index].model = newModel;
                                            setNodeDataKey('models', updatedModels);
                                        }
                                    "
                                    :disabled="false"
                                    to="right"
                                    variant="grey"
                                    teleport
                                    class="grow"
                                />
                                <button
                                    class="text-stone-gray flex-shrink-0 rounded p-1
                                        transition-colors hover:text-red-400"
                                    title="Remove Model"
                                    @click="removeParallelModel(index)"
                                >
                                    <UiIcon name="MaterialSymbolsDeleteRounded" class="h-5 w-5" />
                                </button>
                            </div>
                        </div>
                        <button
                            class="hover:bg-obsidian/20 text-soft-silk/80 mt-1 mr-0 ml-auto flex h-8
                                w-fit cursor-pointer items-center justify-center gap-2 rounded-lg
                                px-3 text-sm font-bold transition-colors"
                            @click="addParallelModel"
                        >
                            <UiIcon name="Fa6SolidPlus" class="h-3 w-3" />
                            <span>Add Model</span>
                        </button>
                    </div>

                    <div class="flex flex-col space-y-2">
                        <h3
                            class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-1 text-sm
                                font-bold"
                        >
                            Aggregator Model
                        </h3>
                        <UiModelsSelect
                            :model="node.data.aggregator.model"
                            :set-model="
                                (model: string) => {
                                    currentModel = model;
                                    setNodeDataKey('aggregator.model', model);
                                }
                            "
                            :disabled="false"
                            to="right"
                            variant="grey"
                            teleport
                        />
                    </div>
                </template>

                <!-- Routing Node Settings -->
                <template v-else-if="node.type === NodeTypeEnum.ROUTING">
                    <div class="flex flex-col space-y-2">
                        <h3
                            class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-1 text-sm
                                font-bold"
                        >
                            Route Template
                        </h3>
                        <UiGraphNodeUtilsRoutingGroupSelect
                            :routing-group-id="node.data.routeGroupId"
                            :set-routing-group-id="
                                (id: string) => setNodeDataKey('routeGroupId', id)
                            "
                            color="grey"
                            class="h-10"
                        />
                    </div>
                </template>
            </div>

            <!-- Empty State -->
            <div
                v-else
                class="flex h-full w-full flex-col items-center justify-center space-y-2
                    text-center"
            >
                <UiIcon name="MajesticonsInformationCircleLine" class="text-stone-gray h-7 w-7" />
                <p class="text-stone-gray text-sm">Select a node to view its properties.</p>
            </div>
        </Transition>
    </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
    transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
    opacity: 0;
}
</style>
