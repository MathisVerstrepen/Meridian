<script lang="ts" setup>
// --- Stores ---
const globalSettingsStore = useSettingsStore();

// --- State from Stores (Reactive Refs) ---
const { generalSettings } = storeToRefs(globalSettingsStore);
</script>

<template>
    <div class="grid h-full w-full grid-cols-[33%_66%] items-center gap-y-8">
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
    </div>
</template>

<style scoped></style>
