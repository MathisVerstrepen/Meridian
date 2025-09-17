<script lang="ts" setup>
// --- Stores ---
const globalSettingsStore = useSettingsStore();

// --- State from Stores ---
const { isReady } = storeToRefs(globalSettingsStore);
</script>

<template>
    <div class="flex h-0 min-h-full w-full flex-col px-10 py-5">
        <header class="border-b-2 border-stone-gray/10 pb-4">
            <h1 class="text-soft-silk flex items-center gap-4 text-3xl font-bold capitalize py-2">
                <slot name="header" />
            </h1>
        </header>
        <main class="w-full flex-1 overflow-y-auto hide-scrollbar pr-4">
            <slot v-if="isReady" />
            <div
                v-else
                class="text-stone-gray z-10 mt-16 w-full animate-pulse text-center font-bold"
            >
                Loading settings...
            </div>
        </main>
    </div>
</template>

<style scoped></style>
