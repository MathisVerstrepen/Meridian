<script lang="ts" setup>
// --- Props ---
defineProps<{
    state: boolean;
    setState: (val: boolean) => void;
}>();

// --- Local State ---
const monted = ref(false);

onMounted(() => {
    monted.value = true;
});
</script>

<template>
    <HeadlessSwitch
        :model-value="state"
        @update:model-value="setState"
        :class="state ? 'bg-ember-glow' : 'bg-stone-gray'"
        class="relative inline-flex h-6 w-11 items-center rounded-full"
        role="switch"
        v-if="monted"
    >
        <span
            :class="state ? 'translate-x-6' : 'translate-x-1'"
            class="bg-anthracite inline-block h-4 w-4 transform rounded-full transition duration-200 ease-in-out"
        ></span>
    </HeadlessSwitch>
    <span v-else class="bg-stone-gray/20 h-6 w-11 animate-pulse rounded-full"></span>
</template>

<style scoped></style>
