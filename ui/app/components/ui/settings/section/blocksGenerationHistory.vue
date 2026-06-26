<script lang="ts" setup>
import { SETTINGS_ENTRY } from '@/constants/settingsEntries';

const settingsStore = useSettingsStore();
const { generationHistorySettings } = storeToRefs(settingsStore);

const generationHistoryEntry = SETTINGS_ENTRY.generationHistorySavedEntries;
const closeOnRestoreEntry = SETTINGS_ENTRY.generationHistoryCloseOnRestore;
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ generationHistoryEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ generationHistoryEntry.description }}
                </p>
            </div>
            <div class="ml-6 w-32 shrink-0">
                <UiSettingsUtilsInputNumber
                    id="saved-generation-history-input"
                    :number="generationHistorySettings.max_saved_entries"
                    placeholder="Default: 10"
                    :min="1"
                    :max="100"
                    :step="1"
                    @update:number="
                        (value: number) => {
                            generationHistorySettings.max_saved_entries = value;
                        }
                    "
                />
            </div>
        </div>

        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ closeOnRestoreEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ closeOnRestoreEntry.description }}
                </p>
            </div>
            <div class="shrink-0">
                <UiSettingsUtilsSwitch
                    id="close-generation-history-on-restore"
                    :state="generationHistorySettings.close_modal_on_restore"
                    :set-state="
                        (value: boolean) => {
                            generationHistorySettings.close_modal_on_restore = value;
                        }
                    "
                />
            </div>
        </div>
    </div>
</template>
