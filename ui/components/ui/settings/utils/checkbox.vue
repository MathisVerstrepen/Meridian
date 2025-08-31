<script lang="ts" setup>
// --- Props ---
defineProps<{
    label: string;
    state: boolean;
    setState: (val: boolean) => void;
    style: 'white' | 'dark';
}>();
</script>

<template>
    <label class="relative inline-flex cursor-pointer items-center">
        <input
            type="checkbox"
            :checked="state"
            class="sr-only"
            @change="setState(($event.target as HTMLInputElement).checked)"
        >

        <div
            class="flex h-5 w-5 items-center justify-center rounded border-2 transition duration-200 ease-in-out"
            :class="{
                'bg-ember-glow border-ember-glow': state,
                'border-stone-gray bg-white': style === 'white' && !state,
                'border-stone-gray/20 bg-obsidian/50': style === 'dark' && !state,
            }"
        >
            <UiIcon
                v-if="state"
                name="MaterialSymbolsCheckSmallRounded"
                class="h-5 w-5 text-white"
            />
            <div
                v-if="!state"
                class="h-4 w-4 rounded"
                :class="{
                    'bg-white': style === 'white',
                    'bg-obsidian/50': style === 'dark',
                }"
            />
        </div>
        <span class="text-stone-gray ml-2 font-medium">{{ label }}</span>
    </label>
</template>

<style scoped></style>
