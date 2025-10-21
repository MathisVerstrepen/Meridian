<script lang="ts" setup>
// --- Stores ---
const settingsStore = useSettingsStore();

// --- State from Stores (Reactive Refs) ---
const { toolsSettings } = storeToRefs(settingsStore);

const availableTools = [
    { id: 'web-search', name: 'Web Search' },
    { id: 'link-extraction', name: 'Link Extraction' },
];

const isToolSelected = (toolId: string) => {
    return toolsSettings.value.defaultSelectedTools?.includes(toolId);
};

const toggleTool = (toolId: string) => {
    if (!toolsSettings.value.defaultSelectedTools) {
        toolsSettings.value.defaultSelectedTools = [];
    }
    const index = toolsSettings.value.defaultSelectedTools.indexOf(toolId);
    if (index > -1) {
        toolsSettings.value.defaultSelectedTools.splice(index, 1);
    } else {
        toolsSettings.value.defaultSelectedTools.push(toolId);
    }
};
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
        <!-- Setting: Default selected tools -->
        <div class="py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Default Selected Tools</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Choose which tools are selected by default when you start a new conversation.
                </p>
            </div>
            <div class="mt-4 flex flex-col gap-2">
                <label
                    v-for="tool in availableTools"
                    :key="tool.id"
                    class="flex cursor-pointer items-center"
                >
                    <UiSettingsUtilsCheckbox
                        :label="tool.name"
                        :model-value="isToolSelected(tool.id)"
                        :style="'dark'"
                        @update:model-value="toggleTool(tool.id)"
                    />
                </label>
            </div>
        </div>
    </div>
</template>

<style scoped></style>
