<script lang="ts" setup>
defineProps<{
    isOpen: boolean;
    modelValue: string;
}>();

const emit = defineEmits<{
    (e: 'update:modelValue', val: string): void;
    (e: 'close'): void;
    (e: 'submit'): void;
}>();
</script>

<template>
    <UiUtilsBaseModal
        :model-value="isOpen"
        title="Rename Item"
        icon="MdiRename"
        size="sm"
        position="absolute"
        :teleport="false"
        :close-on-backdrop="false"
        @close="emit('close')"
    >
        <input
            :value="modelValue"
            type="text"
            class="bg-obsidian/60 border-stone-gray/20 text-soft-silk focus:border-ember-glow/50
                w-full rounded-lg border px-3 py-2.5 text-sm transition-colors focus:outline-none"
            autoFocus
            @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
            @keyup.enter="emit('submit')"
            @keyup.esc="emit('close')"
        />

        <template #footer>
            <button
                class="text-stone-gray hover:text-soft-silk rounded-lg px-4 py-2 text-sm transition-colors"
                @click="emit('close')"
            >
                Cancel
            </button>
            <button
                class="bg-ember-glow hover:bg-ember-glow/90 text-soft-silk rounded-lg px-4 py-2 text-sm
                    font-bold transition-colors"
                @click="emit('submit')"
            >
                Rename
            </button>
        </template>
    </UiUtilsBaseModal>
</template>
