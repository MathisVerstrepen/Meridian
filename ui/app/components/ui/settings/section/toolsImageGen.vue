<script lang="ts" setup>
// --- Stores ---
const settingsStore = useSettingsStore();

// --- State from Stores ---
const { toolsImageGenerationSettings } = storeToRefs(settingsStore);
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
        <!-- Setting: Default Model -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Default Model</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    The default image generation model to use for generating images. You can
                    override this setting on a per-node basis in the graph editor.
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiModelsSelect
                    id="image-generation-default-model"
                    :model="toolsImageGenerationSettings.defaultModel"
                    :set-model="
                        (model: string) => {
                            toolsImageGenerationSettings.defaultModel = model;
                        }
                    "
                    :disabled="false"
                    to="right"
                    from="bottom"
                    variant="grey"
                    class="h-10 w-[20rem]"
                    only-image-models
                    hide-tool
                />
            </div>
        </div>
    </div>
</template>

<style scoped></style>
