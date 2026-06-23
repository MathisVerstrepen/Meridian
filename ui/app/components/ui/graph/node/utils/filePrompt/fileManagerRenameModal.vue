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
            class="bg-obsidian/70 absolute inset-0 z-50 flex items-center justify-center
                backdrop-blur-sm"
            :initial="{ opacity: 0 }"
            :animate="{ opacity: 1 }"
            :exit="{ opacity: 0 }"
        >
            <motion.div
                class="bg-obsidian border-stone-gray/20 flex flex-col gap-4 rounded-2xl border p-6
                    shadow-2xl"
                :initial="{ scale: 0.92, opacity: 0 }"
                :animate="{ scale: 1, opacity: 1, transition: { duration: 0.2, ease: 'easeOut' } }"
                :exit="{ scale: 0.92, opacity: 0, transition: { duration: 0.15, ease: 'easeIn' } }"
            >
                <div class="flex items-center gap-3">
                    <div class="bg-ember-glow/10 flex h-9 w-9 items-center justify-center rounded-lg">
                        <UiIcon name="MdiRename" class="text-ember-glow h-5 w-5" />
                    </div>
                    <h3 class="text-soft-silk text-lg font-semibold">Rename Item</h3>
                </div>
                <input
                    :value="modelValue"
                    type="text"
                    class="bg-obsidian/60 border-stone-gray/20 text-soft-silk focus:border-ember-glow/50
                        w-72 rounded-lg border px-3 py-2.5 text-sm transition-colors focus:outline-none"
                    autoFocus
                    @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
                    @keyup.enter="emit('submit')"
                    @keyup.esc="emit('close')"
                />
                <div class="flex justify-end gap-2">
                    <button
                        class="bg-stone-gray/10 hover:bg-stone-gray/20 text-stone-gray hover:text-soft-silk
                            rounded-lg px-3 py-2 text-sm font-medium transition-colors"
                        @click="emit('close')"
                    >
                        Cancel
                    </button>
                    <button
                        class="bg-ember-glow text-obsidian rounded-lg px-3 py-2 text-sm font-semibold
                            transition-all hover:brightness-110"
                        @click="emit('submit')"
                    >
                        Rename
                    </button>
                </div>
            </motion.div>
        </motion.div>
    </AnimatePresence>
</template>
