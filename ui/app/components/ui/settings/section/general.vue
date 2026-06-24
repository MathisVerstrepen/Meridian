<script lang="ts" setup>
import { SETTINGS_ENTRY } from '@/constants/settingsEntries';
import { NodeTypeEnum } from '@/types/enums';

// --- Stores ---
const globalSettingsStore = useSettingsStore();

// --- State from Stores (Reactive Refs) ---
const { generalSettings } = storeToRefs(globalSettingsStore);

const nodeTypeOptions = [
    { id: NodeTypeEnum.TEXT_TO_TEXT, name: 'Text to Text', icon: 'FluentCodeText16Filled' },
    { id: NodeTypeEnum.ROUTING, name: 'Routing', icon: 'MaterialSymbolsAltRouteRounded' },
    {
        id: NodeTypeEnum.PARALLELIZATION,
        name: 'Parallelization',
        icon: 'HugeiconsDistributeHorizontalCenter',
    },
];
const openChatEntry = SETTINGS_ENTRY.canvasOpenChat;
const thinkingPanelsEntry = SETTINGS_ENTRY.chatThinkingPanels;
const thinkingContextEntry = SETTINGS_ENTRY.chatThinkingContext;
const messageCollapsingEntry = SETTINGS_ENTRY.chatMessageCollapsing;
const defaultNodeTypeEntry = SETTINGS_ENTRY.canvasDefaultNodeType;
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
        <!-- Setting: Open chat view on canvas creation -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ openChatEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ openChatEntry.description }}
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiSettingsUtilsSwitch
                    id="general-open-chat-view-on-new-canvas"
                    :state="generalSettings.openChatViewOnNewCanvas"
                    :set-state="
                        (value: boolean) => {
                            generalSettings.openChatViewOnNewCanvas = value;
                        }
                    "
                />
            </div>
        </div>

        <!-- Setting: Always open thinking panels -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ thinkingPanelsEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ thinkingPanelsEntry.description }}
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiSettingsUtilsSwitch
                    id="general-always-thinking-disclosures"
                    :state="generalSettings.alwaysThinkingDisclosures"
                    :set-state="
                        (value: boolean) => {
                            generalSettings.alwaysThinkingDisclosures = value;
                        }
                    "
                />
            </div>
        </div>

        <!-- Setting: Include thinking in context -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ thinkingContextEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ thinkingContextEntry.description }}
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiSettingsUtilsSwitch
                    id="general-include-thinking-in-context"
                    :state="generalSettings.includeThinkingInContext"
                    :set-state="
                        (value: boolean) => {
                            generalSettings.includeThinkingInContext = value;
                        }
                    "
                />
            </div>
        </div>

        <!-- Setting: Enable Message Collapsing -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ messageCollapsingEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ messageCollapsingEntry.description }}
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiSettingsUtilsSwitch
                    id="general-enable-message-collapsing"
                    :state="generalSettings.enableMessageCollapsing"
                    :set-state="
                        (value: boolean) => {
                            generalSettings.enableMessageCollapsing = value;
                        }
                    "
                />
            </div>
        </div>

        <!-- Setting: Default Node Type -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ defaultNodeTypeEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ defaultNodeTypeEntry.description }}
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiSettingsUtilsSelect
                    id="general-default-node-type"
                    :item-list="nodeTypeOptions"
                    :selected="generalSettings.defaultNodeType"
                    @update:item-value="
                        (value: NodeTypeEnum) => {
                            generalSettings.defaultNodeType = value;
                        }
                    "
                />
            </div>
        </div>
    </div>
</template>

<style scoped></style>
