<script lang="ts" setup>
import { SETTINGS_ENTRY } from '@/constants/settingsEntries';

const settingsStore = useSettingsStore();
const { accountSettings } = storeToRefs(settingsStore);

const openRouterApiKeyEntry = SETTINGS_ENTRY.apiKeysOpenRouter;
</script>

<template>
    <div class="divide-stone-gray/10 flex flex-col divide-y">
        <div class="flex items-center justify-between py-6">
            <div class="max-w-2xl">
                <h3 class="font-semibold">
                    <NuxtLink
                        class="text-soft-silk decoration-stone-gray/40 hover:decoration-stone-gray/60
                            underline decoration-dashed underline-offset-4 transition-colors
                            duration-200 ease-in-out"
                        to="https://openrouter.ai/settings/keys"
                        external
                        target="_blank"
                    >
                        {{ openRouterApiKeyEntry.title }}
                    </NuxtLink>
                </h3>
                <p class="text-stone-gray/80 mt-1 text-sm">
                    {{ openRouterApiKeyEntry.description }}
                </p>
            </div>
            <div class="ml-6 shrink-0">
                <input
                    id="account-api-key"
                    type="password"
                    class="border-stone-gray/20 bg-anthracite/20 text-stone-gray
                        focus:border-ember-glow h-10 w-96 rounded-lg border-2 p-2 transition-colors
                        duration-200 ease-in-out outline-none focus:border-2"
                    placeholder="sk-or-v1-..."
                    :value="accountSettings.openRouterApiKey"
                    @input="
                        (event: Event) => {
                            const target = event.target as HTMLInputElement;
                            accountSettings.openRouterApiKey = target.value;
                        }
                    "
                />
            </div>
        </div>
    </div>
</template>
