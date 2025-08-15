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
    <div class="grid h-full w-full grid-cols-[33%_66%] content-start items-start gap-y-8">
        <label class="flex gap-2" for="general-open-chat-view-on-new-canvas">
            <h3 class="text-stone-gray font-bold">Open chat view on canvas creation</h3>
            <UiSettingsInfobubble>
                When creating a new canvas, the chat view will be opened automatically. This is
                useful for quickly starting a conversation with the model. If disabled, the new
                canvas will start in canvas view.
            </UiSettingsInfobubble>
        </label>
        <UiSettingsUtilsSwitch
            :state="generalSettings.openChatViewOnNewCanvas"
            :set-state="
                (value: boolean) => {
                    generalSettings.openChatViewOnNewCanvas = value;
                }
            "
            id="general-open-chat-view-on-new-canvas"
        ></UiSettingsUtilsSwitch>

        <label class="flex gap-2" for="general-always-thinking-disclosures">
            <h3 class="text-stone-gray font-bold">Always thinking disclosures</h3>
            <UiSettingsInfobubble>
                When enabled, the thinking disclosures will always be opened by default. This is
                useful for users who want to see the model's thought process without having to click
                on the disclosure button. If disabled, the thinking disclosures will be closed by
                default.
            </UiSettingsInfobubble>
        </label>
        <UiSettingsUtilsSwitch
            :state="generalSettings.alwaysThinkingDisclosures"
            :set-state="
                (value: boolean) => {
                    generalSettings.alwaysThinkingDisclosures = value;
                }
            "
            id="general-always-thinking-disclosures"
        ></UiSettingsUtilsSwitch>

        <label class="flex gap-2" for="general-include-thinking-in-context">
            <h3 class="text-stone-gray font-bold">Include thinking in context</h3>
            <UiSettingsInfobubble>
                When enabled, the model's thinking process will be included in the context of the
                conversation. This allows the model to take into account its own thought process
                when generating responses. If disabled, the thinking process will not be included in
                the context. Recommended to False for most users to avoid overwhelming the model
                with too much information and reduce cost.
            </UiSettingsInfobubble>
        </label>
        <UiSettingsUtilsSwitch
            :state="generalSettings.includeThinkingInContext"
            :set-state="
                (value: boolean) => {
                    generalSettings.includeThinkingInContext = value;
                }
            "
            id="general-include-thinking-in-context"
        ></UiSettingsUtilsSwitch>

        <label class="flex gap-2" for="general-default-node-type">
            <h3 class="text-stone-gray font-bold">Default Node Type</h3>
            <UiSettingsInfobubble>
                The default node type to use when creating new nodes in chat view.
            </UiSettingsInfobubble>
        </label>
        <UiSettingsUtilsSelect
            :item-list="nodeTypeOptions"
            :selected="generalSettings.defaultNodeType"
            @update:item-value="
                (value: NodeTypeEnum) => {
                    generalSettings.defaultNodeType = value;
                }
            "
            class="w-[20rem]"
        ></UiSettingsUtilsSelect>
    </div>
</template>

<style scoped></style>
