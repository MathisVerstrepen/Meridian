<script lang="ts" setup>
import { motion } from 'motion-v';

const emit = defineEmits(['update:deleteNode', 'update:executionPlan']);

defineProps<{
    nSelected: number;
}>();
</script>

<template>
    <AnimatePresence>
        <motion.div
            v-if="nSelected && nSelected > 1"
            key="execution-plan"
            :initial="{ opacity: 0, y: -50, width: '40%', height: '3rem' }"
            :animate="{
                opacity: 1,
                y: 0,
                width: 'fit-content',
                height: '3rem',
                transition: {
                    y: { duration: 0.15 },
                    width: { delay: 0.05, duration: 0.2 },
                    height: { duration: 0.3, ease: 'easeInOut' },
                },
            }"
            :exit="{
                opacity: 0,
                y: -50,
                width: '40%',
                height: '3rem',
                transition: {
                    width: { duration: 0.2 },
                    y: { delay: 0.15, duration: 0.1 },
                    height: { duration: 0.3, ease: 'easeInOut' },
                },
            }"
            class="bg-anthracite/75 border-stone-gray/10 flex h-12 flex-col rounded-2xl border-2 p-1 px-2 shadow-lg
                backdrop-blur-md"
        >
            <div
                class="flex h-9 w-full shrink-0 items-center justify-between gap-5 overflow-hidden pl-2"
            >
                <div class="flex items-center gap-2">
                    <UiIcon name="LetsIconsTarget" class="text-soft-silk h-5 w-5" />
                    <span class="text-soft-silk text-sm font-semibold whitespace-nowrap">
                        {{ nSelected }} Selected Nodes
                    </span>
                </div>
                <span class="w-10"/>
                <div class="flex items-center gap-1">
                    <button
                        class="hover:bg-soft-silk/20 flex h-8 w-8 cursor-pointer items-center justify-center rounded-xl
                            transition-colors duration-200 ease-in-out"
                        title="Run selected nodes"
                        @click="emit('update:executionPlan')"
                    >
                        <UiIcon name="CodiconRunAll" class="text-soft-silk h-4 w-4"/>
                    </button>

                    <button
                        class="hover:bg-terracotta-clay/25 text-terracotta-clay flex h-8 w-8 cursor-pointer items-center
                            justify-center rounded-xl transition-colors duration-200 ease-in-out"
                        title="Delete selected nodes"
                        @click.stop="emit('update:deleteNode')"
                    >
                        <UiIcon
                            name="MaterialSymbolsDeleteRounded"
                            class="text-terracotta-clay h-5 w-5"
                        />
                    </button>
                </div>
            </div>
        </motion.div>
    </AnimatePresence>
</template>

<style scoped></style>
