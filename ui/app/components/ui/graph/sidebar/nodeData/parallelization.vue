<script lang="ts" setup>
import type { Node } from '@vue-flow/core';
import { NodeTypeEnum } from '@/types/enums';

const props = defineProps<{
    node: Node;
    setNodeDataKey: (key: string, value: unknown) => void;
    setCurrentModel: (model: string) => void;
}>();

const { generateId } = useUniqueId();

const addParallelModel = () => {
    if (!props.node || props.node.type !== NodeTypeEnum.PARALLELIZATION) return;

    const newModel = {
        model: props.node.data.defaultModel,
        reply: '',
        id: generateId(),
    };
    const updatedModels = [...props.node.data.models, newModel];
    props.setNodeDataKey('models', updatedModels);
};

const removeParallelModel = (index: number) => {
    if (!props.node || props.node.type !== NodeTypeEnum.PARALLELIZATION) return;

    const updatedModels = [...props.node.data.models];
    updatedModels.splice(index, 1);
    props.setNodeDataKey('models', updatedModels);
};
</script>

<template>
    <div class="flex flex-col space-y-2">
        <h3 class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-1 text-sm font-bold">
            Parallel Models
        </h3>
        <div class="flex flex-col gap-2">
            <div
                v-for="(model, index) in node.data.models"
                :key="model.id"
                class="flex w-full items-center gap-2"
            >
                <span class="text-stone-gray font-mono text-xs">#{{ index + 1 }}</span>
                <UiModelsSelect
                    v-if="node.data.models"
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
                    from="bottom"
                    variant="grey"
                    teleport
                    class="grow"
                    prevent-trigger-on-mount
                />
                <button
                    class="text-stone-gray flex-shrink-0 rounded p-1 transition-colors
                        hover:text-red-400"
                    title="Remove Model"
                    @click="removeParallelModel(index)"
                >
                    <UiIcon name="MaterialSymbolsDeleteRounded" class="h-5 w-5" />
                </button>
            </div>
        </div>
        <button
            class="hover:bg-obsidian/20 text-soft-silk/80 mt-1 mr-0 ml-auto flex h-8 w-fit
                cursor-pointer items-center justify-center gap-2 rounded-lg px-3 text-sm font-bold
                transition-colors"
            @click="addParallelModel"
        >
            <UiIcon name="Fa6SolidPlus" class="h-3 w-3" />
            <span>Add Model</span>
        </button>
    </div>

    <div class="flex flex-col space-y-2">
        <h3 class="text-soft-silk bg-obsidian/20 rounded-lg px-3 py-1 text-sm font-bold">
            Aggregator Model
        </h3>
        <UiModelsSelect
            v-if="node.data.aggregator"
            :model="node.data.aggregator.model"
            :set-model="
                (model: string) => {
                    setNodeDataKey('aggregator.model', model);
                }
            "
            :disabled="false"
            to="right"
            from="bottom"
            variant="grey"
            teleport
            prevent-trigger-on-mount
        />
    </div>
</template>

<style scoped></style>
