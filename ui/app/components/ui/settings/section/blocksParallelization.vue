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
    <div class="divide-stone-gray/10 flex flex-col divide-y">
        <!-- Setting: Aggregator Model -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Aggregator Model</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    The default model used to aggregate the results of the parallelized blocks. This
                    model will process the aggregated data and return the final result.
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiModelsSelect
                    id="parallelization-aggregator-model"
                    :model="blockParallelizationSettings.aggregator.model"
                    :set-model="
                        (model: string) => {
                            blockParallelizationSettings.aggregator.model = model;
                        }
                    "
                    :disabled="false"
                    to="right"
                    from="bottom"
                    variant="grey"
                    class="h-10 w-[20rem]"
                />
            </div>
        </div>

        <!-- Setting: Aggregator Prompt -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Aggregator Prompt</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    This prompt is used to aggregate the results of the parallelized blocks. It is
                    sent to the model after all blocks have been processed. You can use this prompt
                    to summarize the results or to ask the model to perform additional processing on
                    the aggregated data.
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <textarea
                    id="parallelization-aggregator-prompt"
                    v-model="blockParallelizationSettings.aggregator.prompt"
                    class="border-stone-gray/20 bg-anthracite/20 text-stone-gray
                        focus:border-ember-glow dark-scrollbar h-32 w-[30rem] rounded-lg border-2
                        p-2 transition-colors duration-200 ease-in-out outline-none focus:border-2"
                />
            </div>
        </div>

        <!-- Setting: Parallelization Models -->
        <div class="py-6">
            <div class="flex items-center justify-between">
                <div class="max-w-2xl">
                    <h3 class="text-soft-silk font-semibold">Parallelization models</h3>
                    <p class="text-stone-gray/80 mt-1 text-sm">
                        The default models used to process the blocks in parallel. Each model will
                        process its own block and return the result. The results will be aggregated
                        by the aggregator model.
                    </p>
                </div>
                <div id="parallelization-models" class="ml-6 flex shrink-0 items-center gap-2">
                    <UiModelsSelect
                        :model="currentModelToAdd || ''"
                        :set-model="
                            (model: string) => {
                                currentModelToAdd = model;
                            }
                        "
                        :disabled="false"
                        to="right"
                        from="bottom"
                        variant="grey"
                        class="h-10 w-[20rem]"
                    />
                    <button
                        class="bg-obsidian/20 dark:border-obsidian/50 border-soft-silk/20
                            text-soft-silk/80 hover:bg-obsidian/30 flex h-10 w-10 cursor-pointer
                            items-center justify-center rounded-2xl border-2 transition-colors
                            duration-200 ease-in-out"
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
            </div>

            <ul
                v-if="isReady && blockParallelizationSettings.models.length"
                class="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3"
            >
                <template v-for="(model, index) in blockParallelizationSettings.models">
                    <li
                        v-for="modelInfo in [getModel(model.model)]"
                        :key="modelInfo.id"
                        class="bg-obsidian/50 border-stone-gray/10 relative flex flex-col
                            justify-center rounded-2xl border-2 px-5 py-3"
                    >
                        <div class="flex items-center gap-5">
                            <span v-if="modelInfo?.icon" class="flex items-center">
                                <UiIcon
                                    :name="'models/' + modelInfo.icon"
                                    class="text-stone-gray h-5 w-5"
                                />
                            </span>
                            <div class="flex flex-col">
                                <span class="text-soft-silk font-bold capitalize">{{
                                    modelInfo.id.split('/')[0]
                                }}</span>
                                <span class="text-stone-gray text-sm capitalize">{{
                                    modelInfo.id.split('/')[1]
                                }}</span>
                            </div>
                        </div>
                        <button
                            class="hover:bg-stone-gray/10 absolute top-2 right-2 flex h-7 w-7
                                items-center justify-center rounded-full transition-colors
                                duration-200 ease-in-out"
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
    </div>
</template>

<style scoped></style>
