<script lang="ts" setup>
// --- Stores ---
const globalSettingsStore = useGlobalSettingsStore();

// --- State from Stores (Reactive Refs) ---
const { excludeReasoning } = storeToRefs(globalSettingsStore);

// --- Actions/Methods from Stores ---
const { defaultModel, setExcludeReasoning } = globalSettingsStore;
</script>

<template>
    <ul class="flex h-full w-full flex-col gap-4">
        <li class="flex w-full items-center gap-8">
            <h3 class="text-stone-gray font-bold">Default Model</h3>
            <UiModelsSelect
                :model="defaultModel"
                :setModel="
                    (model: string) => {
                        defaultModel = model;
                    }
                "
                variant="grey"
                class="h-10 w-[30rem]"
            ></UiModelsSelect>
        </li>
        <li class="flex w-full items-center gap-8">
            <h3 class="text-stone-gray font-bold">Exclude Reasoning</h3>
            <HeadlessSwitch
                v-model="excludeReasoning"
                :setModel="setExcludeReasoning"
                :class="excludeReasoning ? 'bg-blue-600' : 'bg-gray-200'"
                class="relative inline-flex h-6 w-11 items-center rounded-full"
            >
                <span class="sr-only">Enable notifications</span>
                <span
                    :class="excludeReasoning ? 'translate-x-6' : 'translate-x-1'"
                    class="inline-block h-4 w-4 transform rounded-full bg-white transition"
                ></span>
            </HeadlessSwitch>
        </li>
    </ul>
</template>

<style scoped></style>
