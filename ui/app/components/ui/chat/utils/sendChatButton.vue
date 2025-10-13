<script lang="ts" setup>
import type { BlockDefinition } from '@/types/graph';
import { motion } from 'motion-v';

const emit = defineEmits(['send', 'cancelStream', 'selectNodeType']);

defineProps<{
    isStreaming: boolean;
    isEmpty: boolean;
    isUploading: boolean;
}>();

// --- Stores ---
const globalSettingsStore = useSettingsStore();

// --- State from Stores (Reactive Refs) ---
const { generalSettings, isReady } = storeToRefs(globalSettingsStore);

// --- Composables ---
const { getBlockById, getBlockByNodeType } = useBlocks();

// --- Local state ---
const selectMenuOpen = ref(false);
const selectedNodeType = ref<BlockDefinition | undefined>();
const buttonRef = ref<HTMLElement | null>(null);
const menuPosition = ref({ top: 0, left: 0 });

const updateMenuPosition = () => {
    if (buttonRef.value) {
        const rect = buttonRef.value.getBoundingClientRect();
        menuPosition.value = {
            top: rect.top - 132,
            left: rect.left - 175,
        };
    }
};

const toggleMenu = () => {
    selectMenuOpen.value = !selectMenuOpen.value;
    if (selectMenuOpen.value) {
        nextTick(() => updateMenuPosition());
    }
};

watch(
    selectedNodeType,
    (newType) => {
        emit('selectNodeType', newType);
    },
    { immediate: true },
);

watch(isReady, (ready) => {
    if (ready) {
        selectedNodeType.value = getBlockByNodeType(generalSettings.value.defaultNodeType);
    }
});

onMounted(() => {
    selectedNodeType.value = getBlockByNodeType(generalSettings.value.defaultNodeType);

    window.addEventListener('resize', updateMenuPosition);
});

onUnmounted(() => {
    window.removeEventListener('resize', updateMenuPosition);
});
</script>

<template>
    <div class="relative flex gap-1">
        <button
            v-if="!isStreaming"
            :disabled="isEmpty || isUploading"
            title="Send message"
            class="dark:bg-stone-gray dark:hover:bg-stone-gray/80 bg-soft-silk hover:bg-soft-silk/80 flex h-12 w-12
                items-center justify-center rounded-l-2xl rounded-r-sm shadow transition duration-200 ease-in-out
                hover:cursor-pointer disabled:opacity-50 disabled:hover:cursor-not-allowed"
            @click="emit('send')"
        >
            <UiIcon name="IconamoonSendFill" class="text-obsidian h-6 w-6" />
        </button>
        <button
            v-else
            title="Cancel streaming"
            class="dark:bg-stone-gray dark:hover:bg-stone-gray/80 bg-soft-silk hover:bg-soft-silk/80 flex h-12 w-12
                items-center justify-center rounded-l-2xl rounded-r-sm shadow transition duration-200 ease-in-out
                hover:cursor-pointer disabled:opacity-50 disabled:hover:cursor-not-allowed"
            @click="emit('cancelStream')"
        >
            <UiIcon name="MaterialSymbolsStopRounded" class="h-6 w-6" />
        </button>

        <button
            v-if="selectedNodeType"
            ref="buttonRef"
            class="relative flex h-12 w-4 items-center justify-center rounded-l-sm rounded-r-2xl shadow transition
                duration-200 ease-in-out hover:cursor-pointer disabled:opacity-50 disabled:hover:cursor-not-allowed"
            :style="{
                backgroundColor: selectedNodeType.color,
            }"
            :class="{
                'hover:brightness-80': !selectMenuOpen,
            }"
            title="Select node type"
            @click="toggleMenu"
        />
        <div
            v-else
            class="dark:bg-stone-gray bg-soft-silk relative flex h-12 w-4 rounded-l-sm rounded-r-2xl opacity-50 shadow"
        />

        <Teleport to="body">
            <!-- Handle click outside -->
            <div v-if="selectMenuOpen" class="fixed inset-0 z-40" @click="toggleMenu"></div>

            <AnimatePresence>
                <motion.div
                    v-if="selectMenuOpen && selectedNodeType"
                    key="chat-select-node-menu"
                    :style="{
                        position: 'fixed',
                        top: `${menuPosition.top}px`,
                        left: `${menuPosition.left}px`,
                    }"
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
                    class="bg-anthracite/80 dark:bg-obsidian/25 border-stone-gray/10 text-stone-gray z-50 mt-2 w-48 rounded-lg
                        border shadow-lg backdrop-blur-lg"
                >
                    <ul class="py-1 pl-1">
                        <template
                            v-for="bloc in [
                                getBlockById('primary-model-text-to-text'),
                                getBlockById('primary-model-routing'),
                                getBlockById('primary-model-parallelization'),
                            ]"
                            :key="bloc?.id"
                        >
                            <li
                                v-if="bloc"
                                class="hover:bg-stone-gray/20 group relative flex cursor-pointer gap-2 rounded px-3 py-2 text-sm
                                    transition-colors duration-200"
                                @click="selectedNodeType = bloc"
                            >
                                <UiIcon :name="bloc.icon" class="h-4 w-4 self-center" />
                                <p class="self-center">
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
        </Teleport>

        <span
            v-if="selectMenuOpen"
            class="fixed top-0 right-0 z-40 h-full w-full"
            @click="selectMenuOpen = false"
        />
    </div>
</template>

<style scoped></style>
