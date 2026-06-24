<script lang="ts" setup>
import { SETTINGS_ENTRY } from '@/constants/settingsEntries';
import { NodeTypeEnum } from '@/types/enums';

const globalSettingsStore = useSettingsStore();
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
const defaultNodeTypeEntry = SETTINGS_ENTRY.canvasDefaultNodeType;
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
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
