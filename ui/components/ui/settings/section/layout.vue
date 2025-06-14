<script lang="ts" setup>
// --- Stores ---
const globalSettingsStore = useSettingsStore();

// --- State from Stores ---
const { isReady } = storeToRefs(globalSettingsStore);
</script>

<template>
    <div class="flex h-0 min-h-full w-full flex-col gap-8 px-10 py-1">
        <header>
            <h1 class="text-stone-gray flex items-center gap-4 text-3xl font-bold capitalize">
                <slot name="header"></slot>
            </h1>
        </header>
        <main class="w-full flex-1 overflow-y-auto">
            <slot v-if="isReady"></slot>
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
