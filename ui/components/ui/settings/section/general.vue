<script lang="ts" setup>
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
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
        <!-- Setting: Open chat view on canvas creation -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Open chat view on canvas creation</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    When creating a new canvas, the chat view will be opened automatically. If
                    disabled, the new canvas will start in canvas view.
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
                <h3 class="text-soft-silk font-semibold">Always open thinking panels</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    When enabled, the thinking panels in the chat view will always be opened by
                    default. If disabled, they will be collapsed by default.
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
                <h3 class="text-soft-silk font-semibold">Include thinking in context</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    When enabled, previous model's thinking process will be included in the context
                    of the conversation. This allows the model to consider its own thought process.
                    Recommended to be OFF for most users to reduce cost and avoid overwhelming the
                    model.
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

        <!-- Setting: Default Node Type -->
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Default Node Type</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    The default node type to use when creating new nodes in chat view.
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiSettingsUtilsSelect
                    id="general-default-node-type"
                    :item-list="nodeTypeOptions"
                    :selected="generalSettings.defaultNodeType"
                    class="w-64"
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
