<script lang="ts" setup>
const model = defineModel<boolean>();

defineProps<{
    label: string;
}>();

defineEmits<{
    (e: 'setState', val: boolean): void;
}>();
</script>

<template>
    <label class="relative inline-flex cursor-pointer items-center">
        <input
            type="checkbox"
            :checked="model"
            @change="(e) => $emit('setState', (e.target as HTMLInputElement).checked)"
            class="sr-only"
        />

        <div
            class="border-stone-gray/20 bg-obsidian/50 mr-2 flex h-5 w-5 items-center justify-center rounded border-2
                transition duration-200 ease-in-out"
            :class="{
                '!bg-ember-glow/30 !border-ember-glow/50': model,
            }"
        >
            <UiIcon
                v-if="model"
                name="MaterialSymbolsCheckSmallRounded"
                class="h-5 w-5 text-white"
            />
            <div v-if="!model" class="bg-obsidian/50 h-4 w-4 rounded"></div>
        </div>
        <span
            class="text-soft-silk/90 hover:text-soft-silk cursor-pointer transition-colors select-none"
            >{{ label }}</span
        >
    </label>
</template>

<style scoped></style>
