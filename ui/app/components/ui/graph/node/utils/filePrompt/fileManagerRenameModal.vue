<script lang="ts" setup>
import { AnimatePresence, motion } from 'motion-v';

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
    <AnimatePresence>
        <motion.div
            v-if="isOpen"
            class="bg-obsidian/80 absolute inset-0 z-50 flex items-center justify-center
                backdrop-blur-sm"
            :initial="{ opacity: 0 }"
            :animate="{ opacity: 1 }"
            :exit="{ opacity: 0 }"
        >
            <div
                class="bg-obsidian border-stone-gray/20 flex flex-col gap-4 rounded-xl border p-6
                    shadow-xl"
            >
                <h3 class="text-soft-silk/80 text-lg font-semibold">Rename Item</h3>
                <input
                    :value="modelValue"
                    type="text"
                    class="bg-obsidian border-stone-gray/20 text-soft-silk focus:border-ember-glow
                        w-64 rounded-lg border px-3 py-2 text-sm focus:outline-none"
                    autoFocus
                    @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
                    @keyup.enter="emit('submit')"
                    @keyup.esc="emit('close')"
                />
                <div class="flex justify-end gap-2">
                    <button
                        class="hover:bg-stone-gray/10 text-stone-gray rounded px-3 py-1.5 text-sm"
                        @click="emit('close')"
                    >
                        Cancel
                    </button>
                    <button
                        class="bg-ember-glow text-soft-silk rounded px-3 py-1.5 text-sm"
                        @click="emit('submit')"
                    >
                        Rename
                    </button>
                </div>
            </div>
        </motion.div>
    </AnimatePresence>
</template>
