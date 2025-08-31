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
        v-if="monted"
        :model-value="state"
        :class="state ? 'bg-ember-glow' : 'bg-stone-gray'"
        class="relative inline-flex h-6 w-11 items-center rounded-full"
        role="switch"
        @update:model-value="setState"
    >
        <span
            :class="state ? 'translate-x-6' : 'translate-x-1'"
            class="bg-anthracite inline-block h-4 w-4 transform rounded-full transition duration-200 ease-in-out"
        />
    </HeadlessSwitch>
    <span v-else class="bg-stone-gray/20 h-6 w-11 animate-pulse rounded-full"/>
</template>

<style scoped></style>
