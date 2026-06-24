<script lang="ts" setup>
import { SETTINGS_ENTRY } from '@/constants/settingsEntries';

const settingsStore = useSettingsStore();
const { blockGithubSettings } = storeToRefs(settingsStore);
const autoPullEntry = SETTINGS_ENTRY.repositoriesAutoPull;
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">{{ autoPullEntry.title }}</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ autoPullEntry.description }}
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <UiSettingsUtilsSwitch
                    id="github-auto-pull"
                    :state="blockGithubSettings.autoPull"
                    :set-state="
                        (value: boolean) => {
                            blockGithubSettings.autoPull = value;
                        }
                    "
                />
            </div>
        </div>
    </div>
</template>
