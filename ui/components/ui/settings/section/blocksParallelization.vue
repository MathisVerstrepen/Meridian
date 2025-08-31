<script lang="ts" setup>
// --- Stores ---
const globalSettingsStore = useSettingsStore();
const modelStore = useModelStore();

// --- State from Stores (Reactive Refs) ---
const { blockParallelizationSettings } = storeToRefs(globalSettingsStore);
const { isReady } = storeToRefs(modelStore);

// --- Actions/Methods from Stores ---
const { getModel } = modelStore;

// --- Local State ---
const currentModelToAdd = ref<string | null>(null);
</script>

<template>
    <div class="grid h-full w-full grid-cols-[33%_66%] content-start items-start gap-y-8">
        <label class="flex gap-2" for="parallelization-aggregator-model">
            <h3 class="text-stone-gray font-bold">Aggregator Model</h3>
            <UiSettingsInfobubble>
                The model used to aggregate the results of the parallelized blocks. This model will
                process the aggregated data and return the final result.
            </UiSettingsInfobubble>
        </label>
        <UiModelsSelect
            id="parallelization-aggregator-model"
            :model="blockParallelizationSettings.aggregator.model"
            :set-model="
                (model: string) => {
                    blockParallelizationSettings.aggregator.model = model;
                }
            "
            :disabled="false"
            variant="grey"
            class="h-10 w-[20rem]"
        />

        <label class="flex gap-2" for="parallelization-aggregator-prompt">
            <h3 class="text-stone-gray font-bold">Aggregator Prompt</h3>
            <UiSettingsInfobubble>
                This prompt is used to aggregate the results of the parallelized blocks. It is sent
                to the model after all blocks have been processed. You can use this prompt to
                summarize the results or to ask the model to perform additional processing on the
                aggregated data.
            </UiSettingsInfobubble>
        </label>
        <textarea
            id="parallelization-aggregator-prompt"
            v-model="blockParallelizationSettings.aggregator.prompt"
            :setModel="
                (value: string) => {
                    blockParallelizationSettings.aggregator.prompt = value;
                }
            "
            class="border-stone-gray/20 bg-anthracite/20 text-stone-gray focus:border-ember-glow h-32 w-[30rem]
                rounded-lg border-2 p-2 transition-colors duration-200 ease-in-out outline-none focus:border-2"
        />

        <label class="flex gap-2" for="parallelization-models">
            <h3 class="text-stone-gray font-bold">Parallelization models</h3>
            <UiSettingsInfobubble>
                The models used to process the blocks in parallel. You can add multiple models to
                this list. Each model will process its own block and return the result. The results
                will be aggregated by the aggregator model.
            </UiSettingsInfobubble>
        </label>
        <div id="parallelization-models" class="flex items-center gap-2">
            <UiModelsSelect
                :model="currentModelToAdd || ''"
                :set-model="
                    (model: string) => {
                        currentModelToAdd = model;
                    }
                "
                :disabled="false"
                variant="grey"
                class="h-10 w-[20rem]"
            />
            <button
                class="bg-stone-gray/10 hover:bg-stone-gray/20 flex cursor-pointer items-center justify-center rounded-2xl
                    p-2 transition-colors duration-200 ease-in-out"
                @click="
                    () => {
                        if (currentModelToAdd) {
                            blockParallelizationSettings.models.push({
                                model: currentModelToAdd,
                            });
                            currentModelToAdd = null;
                        }
                    }
                "
            >
                <UiIcon name="Fa6SolidPlus" class="text-stone-gray h-5 w-5" />
            </button>
        </div>

        <ul v-if="isReady" class="col-span-2 flex w-full flex-wrap gap-2 rounded-2xl p-2">
            <template v-for="(model, index) in blockParallelizationSettings.models">
                <li
                    v-for="modelInfo in [getModel(model.model)]"
                    :key="modelInfo.id"
                    class="border-stone-gray/20 bg-anthracite/20 text-stone-gray relative grid h-20 w-60 grid-cols-[1fr_6fr]
                        rounded-2xl border-2 px-4 py-2"
                >
                    <span
                        v-if="modelInfo?.icon"
                        class="flex h-full translate-y-[1px] items-center self-center"
                    >
                        <UiIcon :name="'models/' + modelInfo.icon" class="h-4 w-4" />
                    </span>
                    <span class="self-center font-bold capitalize">{{
                        modelInfo.id.split('/')[0]
                    }}</span>
                    <span class="col-span-2 capitalize">{{ modelInfo.id.split('/')[1] }}</span>
                    <button
                        class="hover:bg-stone-gray/10 absolute top-2 right-2 flex h-8 w-8 items-center justify-center rounded-full
                            transition-colors duration-200 ease-in-out"
                        @click="
                            () => {
                                blockParallelizationSettings.models.splice(index, 1);
                            }
                        "
                    >
                        <UiIcon name="MaterialSymbolsClose" class="text-stone-gray h-5 w-5" />
                    </button>
                </li>
            </template>
        </ul>
    </div>
</template>

<style scoped></style>
