<script lang="ts" setup>
// --- Props & Emits ---
defineProps<{
    label: string;
    modelValue: boolean;
    style: 'white' | 'dark';
}>();
const emit = defineEmits(['update:modelValue']);
</script>

<template>
    <label class="relative inline-flex cursor-pointer items-center">
        <input
            type="checkbox"
            :checked="modelValue"
            class="sr-only"
            @change="emit('update:modelValue', ($event.target as HTMLInputElement).checked)"
        />

        <div
            class="flex h-5 w-5 items-center justify-center rounded border-2 transition duration-200 ease-in-out"
            :class="{
                'bg-ember-glow border-ember-glow': modelValue,
                'border-stone-gray bg-white': style === 'white' && !modelValue,
                'border-stone-gray/20 bg-obsidian/50': style === 'dark' && !modelValue,
            }"
        >
            <UiIcon
                v-if="modelValue"
                name="MaterialSymbolsCheckSmallRounded"
                class="h-5 w-5 text-white"
            />
        </div>
        <span class="text-stone-gray ml-2 font-medium">{{ label }}</span>
    </label>
</template>

<style scoped></style>
