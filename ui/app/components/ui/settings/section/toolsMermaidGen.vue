<script lang="ts" setup>
// --- Stores ---
const settingsStore = useSettingsStore();

// --- State from Stores ---
const { toolsMermaidGenerationSettings } = storeToRefs(settingsStore);
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Default Model</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    The model used by the Mermaid tool when a node delegates diagram generation.
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiModelsSelect
                    id="mermaid-generation-default-model"
                    :model="toolsMermaidGenerationSettings.defaultModel"
                    :set-model="
                        (model: string) => {
                            toolsMermaidGenerationSettings.defaultModel = model;
                        }
                    "
                    :disabled="false"
                    to="right"
                    from="bottom"
                    variant="grey"
                    class="h-10 w-[20rem]"
                    hide-tool
                />
            </div>
        </div>

        <div class="py-6">
            <div class="max-w-3xl">
                <h3 class="text-soft-silk font-semibold">System Prompt</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    This prompt is used only by the Mermaid tool's delegated model, not by the main
                    conversation model.
                </p>
            </div>
            <textarea
                v-model="toolsMermaidGenerationSettings.systemPrompt"
                class="custom_scroll bg-anthracite/75 border-stone-gray/20 text-soft-silk focus:border-ember-glow
                    focus:ring-ember-glow mt-4 block h-72 w-full rounded-md border p-3 text-sm"
                placeholder="Enter Mermaid tool system prompt..."
            ></textarea>
        </div>
    </div>
</template>

<style scoped></style>
