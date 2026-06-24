<script lang="ts" setup>
const globalSettingsStore = useSettingsStore();
const { generalSettings } = storeToRefs(globalSettingsStore);
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Always Open Thinking Panels</h3>
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

        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Include Thinking In Context</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    When enabled, previous model's thinking process will be included in the context
                    of the conversation. Recommended to be OFF for most users to reduce cost and
                    avoid overwhelming the model.
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

        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Enable Message Collapsing</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    When enabled, long user messages will be collapsed by default to improve
                    readability. Users can expand or collapse messages as needed.
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
    </div>
</template>
