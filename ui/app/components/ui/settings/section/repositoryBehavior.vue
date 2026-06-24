<script lang="ts" setup>
const settingsStore = useSettingsStore();
const { blockGithubSettings } = storeToRefs(settingsStore);
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="text-soft-silk font-semibold">Auto Pull</h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    Automatically pull the latest changes from the repository. This is triggered
                    when a block using the repository is executed or when you open the file
                    selection.
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
