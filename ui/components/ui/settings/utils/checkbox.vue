<script lang="ts" setup>
// --- Props ---
defineProps<{
    label: string;
    state: boolean;
    setState: (val: boolean) => void;
}>();

// --- Local State ---
const mounted = ref(false);

onMounted(() => {
    mounted.value = true;
});
</script>

<template>
    <label class="relative inline-flex cursor-pointer items-center" v-if="mounted">
        <input
            type="checkbox"
            :checked="state"
            @change="setState(($event.target as HTMLInputElement).checked)"
            class="sr-only"
        />
        <div
            :class="state ? 'bg-ember-glow border-ember-glow' : 'border-stone-gray bg-white'"
            class="flex h-5 w-5 items-center justify-center rounded border-2 transition duration-200 ease-in-out"
        >
            <UiIcon
                v-if="state"
                name="MaterialSymbolsCheckSmallRounded"
                class="h-5 w-5 text-white"
            />
            <div v-if="!state" class="h-5 w-5 rounded-full bg-white"></div>
        </div>
        <span class="text-stone-gray ml-2 font-medium">{{ label }}</span>
    </label>
    <div v-else class="bg-stone-gray/20 h-5 w-5 animate-pulse rounded"></div>
</template>

<style scoped></style>
