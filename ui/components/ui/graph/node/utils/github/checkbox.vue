<script lang="ts" setup>
const model = defineModel<boolean>();

const props = defineProps<{
    label: string;
    indeterminate?: boolean;
}>();

defineEmits<{
    (e: 'setState', val: boolean): void;
}>();

// --- State ---
const inputRef = ref<HTMLInputElement | null>(null);

// --- Computed ---
watch(
    () => props.indeterminate,
    (isIndeterminate) => {
        if (inputRef.value) {
            inputRef.value.indeterminate = !!isIndeterminate;
        }
    },
    { immediate: true },
);

// --- Lifecycle Hooks ---
onMounted(() => {
    if (inputRef.value) {
        inputRef.value.indeterminate = !!props.indeterminate;
    }
});
</script>

<template>
    <label class="relative inline-flex cursor-pointer items-center">
        <input
            ref="inputRef"
            type="checkbox"
            :checked="model"
            @change="(e) => $emit('setState', (e.target as HTMLInputElement).checked)"
            class="sr-only"
        />

        <div
            class="border-stone-gray/20 bg-obsidian/50 mr-2 flex h-5 w-5 items-center justify-center rounded border-2
                transition duration-200 ease-in-out"
            :class="{
                '!bg-ember-glow/30 !border-ember-glow/50': model || indeterminate,
            }"
        >
            <UiIcon
                v-if="model && !indeterminate"
                name="MaterialSymbolsCheckSmallRounded"
                class="text-ember-glow h-5 w-5"
            />
            <div v-if="indeterminate" class="bg-ember-glow h-0.5 w-2 rounded-sm"></div>
            <div v-if="!model && !indeterminate" class="bg-obsidian/50 h-4 w-4 rounded"></div>
        </div>
        <span
            class="text-soft-silk/90 hover:text-soft-silk cursor-pointer transition-colors select-none"
            >{{ label }}</span
        >
    </label>
</template>

<style scoped></style>
