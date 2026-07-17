<script lang="ts" setup>
import { SETTINGS_ENTRY } from '@/constants/settingsEntries';
import { NodeCategoryEnum } from '@/types/enums';
import type { QuickWorkflowDirection, QuickWorkflowSettingsKey } from '@/utils/quickWorkflow';
import { getQuickWorkflowConfig } from '@/utils/quickWorkflow';

// --- Stores ---
const globalSettingsStore = useSettingsStore();

// --- State from Stores (Reactive Refs) ---
const { blockSettings } = storeToRefs(globalSettingsStore);
const contextWheelEntry = SETTINGS_ENTRY.blocksContextWheel;

const wheelEditors: Array<{
    title: string;
    description: string;
    category: NodeCategoryEnum;
    direction: QuickWorkflowDirection;
    settingsKey: QuickWorkflowSettingsKey;
}> = [
    {
        title: 'Context input',
        description: 'Create a generator upstream and connect its context output to this handle.',
        category: NodeCategoryEnum.CONTEXT,
        direction: 'target',
        settingsKey: 'contextInputWheel',
    },
    {
        title: 'Context output',
        description: 'Create a generator downstream from this context handle.',
        category: NodeCategoryEnum.CONTEXT,
        direction: 'source',
        settingsKey: 'contextWheel',
    },
    {
        title: 'Prompt input',
        description: 'Create a prompt upstream and connect it to this prompt handle.',
        category: NodeCategoryEnum.PROMPT,
        direction: 'target',
        settingsKey: 'promptInputWheel',
    },
    {
        title: 'Prompt output',
        description: 'Create a compatible generator downstream from this prompt handle.',
        category: NodeCategoryEnum.PROMPT,
        direction: 'source',
        settingsKey: 'promptOutputWheel',
    },
    {
        title: 'Attachment input',
        description: 'Create an attachment source upstream and connect it to this handle.',
        category: NodeCategoryEnum.ATTACHMENT,
        direction: 'target',
        settingsKey: 'attachmentInputWheel',
    },
    {
        title: 'Attachment output',
        description: 'Create a compatible generator downstream from this attachment handle.',
        category: NodeCategoryEnum.ATTACHMENT,
        direction: 'source',
        settingsKey: 'attachmentOutputWheel',
    },
];
</script>

<template>
    <div class="flex flex-col divide-y divide-stone-gray/10">
        <div class="py-6">
            <div class="max-w-3xl">
                <h3 class="text-soft-silk font-semibold">
                    {{ contextWheelEntry.title }}
                </h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ contextWheelEntry.description }}
                </p>
            </div>
        </div>
        <div v-for="editor in wheelEditors" :key="editor.settingsKey" class="py-6">
            <div class="max-w-3xl">
                <h4 class="text-soft-silk font-semibold">{{ editor.title }}</h4>
                <p class="text-stone-gray/80 mt-1 text-sm">{{ editor.description }}</p>
            </div>
            <UiSettingsSectionWheelCreator
                class="mt-4"
                :slots="blockSettings[editor.settingsKey]"
                :allowed-main-blocks="getQuickWorkflowConfig(editor.category, editor.direction).allowedMainBlocks"
                :allowed-options="getQuickWorkflowConfig(editor.category, editor.direction).allowedOptions"
            />
        </div>
    </div>
</template>

<style scoped></style>
