<script lang="ts" setup>
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
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Open Chat View On Canvas Creation</h3>
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
