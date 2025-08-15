<script lang="ts" setup>
import type { BlockDefinition } from '@/types/graph';
import { motion } from 'motion-v';

const emit = defineEmits(['send', 'cancelStream', 'selectNodeType']);

defineProps<{
    isStreaming: boolean;
    isEmpty: boolean;
    isUploading: boolean;
}>();

// --- Composables ---
const { getBlockById } = useBlocks();

// --- Local state ---
const selectMenuOpen = ref(false);
const selectedNodeType = ref<BlockDefinition>(
    getBlockById('primary-model-text-to-text') as BlockDefinition,
);

watch(
    selectedNodeType,
    (newType) => {
        emit('selectNodeType', newType);
    },
    { immediate: true },
);
</script>

<template>
    <div class="relative flex gap-1">
        <button
            v-if="!isStreaming"
            :disabled="isEmpty || isUploading"
            title="Send message"
            @click="emit('send')"
            class="dark:bg-stone-gray dark:hover:bg-stone-gray/80 bg-soft-silk hover:bg-soft-silk/80 flex h-12 w-12
                items-center justify-center rounded-l-2xl rounded-r-sm shadow transition duration-200 ease-in-out
                hover:cursor-pointer disabled:opacity-50 disabled:hover:cursor-not-allowed"
        >
            <UiIcon name="IconamoonSendFill" class="text-obsidian h-6 w-6" />
        </button>
        <button
            v-else
            title="Cancel streaming"
            @click="emit('cancelStream')"
            class="dark:bg-stone-gray dark:hover:bg-stone-gray/80 bg-soft-silk hover:bg-soft-silk/80 flex h-12 w-12
                items-center justify-center rounded-l-2xl rounded-r-sm shadow transition duration-200 ease-in-out
                hover:cursor-pointer disabled:opacity-50 disabled:hover:cursor-not-allowed"
        >
            <UiIcon name="MaterialSymbolsStopRounded" class="h-6 w-6" />
        </button>

        <button
            class="relative flex h-12 w-4 items-center justify-center rounded-l-sm rounded-r-2xl shadow transition
                duration-200 ease-in-out hover:cursor-pointer disabled:opacity-50 disabled:hover:cursor-not-allowed"
            :style="{
                backgroundColor: selectedNodeType.color,
            }"
            :class="{
                'hover:brightness-80': !selectMenuOpen,
            }"
            title="Select node type"
            @click="selectMenuOpen = !selectMenuOpen"
        ></button>

        <AnimatePresence>
            <motion.div
                v-if="selectMenuOpen"
                key="chat-select-node-menu"
                :initial="{
                    opacity: 0,
                    scale: 0.3,
                    transformOrigin: 'bottom right',
                }"
                :animate="{
                    opacity: 1,
                    scale: 1,
                    transition: {
                        type: 'spring',
                        stiffness: 300,
                        damping: 25,
                        mass: 0.8,
                    },
                }"
                :exit="{
                    opacity: 0,
                    scale: 0.3,
                    transition: {
                        duration: 0.15,
                        ease: 'easeInOut',
                    },
                }"
                :transition="{ type: 'spring', stiffness: 400, damping: 25 }"
                class="bg-soft-silk/80 absolute right-0 bottom-14 z-10 mt-2 w-48 rounded-lg shadow-lg backdrop-blur"
            >
                <ul class="py-1 pl-1">
                    <template
                        v-for="bloc in [
                            getBlockById('primary-model-text-to-text'),
                            getBlockById('primary-model-routing'),
                            getBlockById('primary-model-parallelization'),
                        ]"
                    >
                        <li
                            v-if="bloc"
                            class="text-obsidian hover:bg-anthracite/20 group relative flex cursor-pointer gap-2 rounded px-3 py-2
                                text-sm transition-colors duration-200"
                            @click="selectedNodeType = bloc"
                        >
                            <UiIcon
                                :name="bloc.icon"
                                class="dark:text-obsidian text-soft-silk h-4 w-4 self-center"
                            />
                            <p class="dark:text-obsidian text-soft-silk self-center">
                                {{ bloc.name }}
                            </p>

                            <span
                                class="absolute top-1/2 right-0 flex h-6 w-2 -translate-y-1/2 items-center justify-center rounded-l-lg
                                    text-transparent transition-all duration-200 group-hover:w-3"
                                :class="{
                                    '!text-soft-silk !w-5':
                                        selectedNodeType.nodeType === bloc.nodeType,
                                }"
                                :style="'background-color: ' + bloc.color"
                            >
                                ✓
                            </span>
                        </li>
                    </template>
                </ul>
            </motion.div>
        </AnimatePresence>
    </div>
</template>

<style scoped></style>
