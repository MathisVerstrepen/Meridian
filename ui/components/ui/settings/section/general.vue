<script lang="ts" setup>
// --- Stores ---
const globalSettingsStore = useSettingsStore();

// --- State from Stores (Reactive Refs) ---
const { generalSettings } = storeToRefs(globalSettingsStore);
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
    </div>
</template>

<style scoped></style>
