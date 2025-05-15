<script lang="ts" setup>
// --- Stores ---
const globalSettingsStore = useGlobalSettingsStore();

// --- State from Stores (Reactive Refs) ---
const { generalSettings } = storeToRefs(globalSettingsStore);
</script>

<template>
    <div class="grid h-full w-full grid-cols-[33%_66%] items-center gap-y-8"></div>
</template>

<style scoped></style>
