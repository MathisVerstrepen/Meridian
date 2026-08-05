<script lang="ts" setup>
import { motion } from 'motion-v';

const emit = defineEmits<{
    (e: 'open-cloud-select'): void;
    (e: 'add-files', files: FileList): void;
    (e: 'add-git-context', tab: 'files' | 'issues'): void;
}>();

// --- Props ---
const props = defineProps<{
    disabled?: boolean;
}>();

// --- Local state ---
const isMenuOpen = ref(false);
const menuRef = ref<HTMLElement | { $el?: HTMLElement } | null>(null);
const buttonRef = ref<HTMLElement | null>(null);
const menuPosition = ref({ top: 0, left: 0 });

const updateMenuPosition = () => {
    const menuElement =
        menuRef.value instanceof HTMLElement ? menuRef.value : menuRef.value?.$el;
    if (buttonRef.value && menuElement) {
        const rect = buttonRef.value.getBoundingClientRect();
        // Layout dimensions ignore motion's initial scale transform.
        const menuWidth = menuElement.offsetWidth;
        const menuHeight = menuElement.offsetHeight;
        const viewportPadding = 8;
        menuPosition.value = {
            top: Math.max(viewportPadding, rect.top - menuHeight - viewportPadding),
            left: Math.max(
                viewportPadding,
                Math.min(rect.left, window.innerWidth - menuWidth - viewportPadding),
            ),
        };
    }
};

const toggleMenu = () => {
    if (props.disabled) return;
    isMenuOpen.value = !isMenuOpen.value;
    if (isMenuOpen.value) {
        nextTick(() => updateMenuPosition());
    }
};

const closeMenu = () => {
    isMenuOpen.value = false;
};

const handleFileChange = (e: Event) => {
    const target = e.target as HTMLInputElement;
    if (target.files) {
        emit('add-files', target.files);
    }
    closeMenu();
};

const handleCloudSelect = () => {
    emit('open-cloud-select');
    closeMenu();
};

const handleGitSelect = (tab: 'files' | 'issues') => {
    emit('add-git-context', tab);
    closeMenu();
};

// Update position on window resize
onMounted(() => {
    window.addEventListener('resize', updateMenuPosition);
});

onUnmounted(() => {
    window.removeEventListener('resize', updateMenuPosition);
});
</script>

<template>
    <div class="relative">
        <!-- Button mode -->
        <button
            ref="buttonRef"
            class="bg-stone-gray/10 hover:bg-stone-gray/20 relative flex h-12 w-12 items-center justify-center
                rounded-2xl shadow transition duration-200 ease-in-out hover:cursor-pointer
                disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="disabled"
            type="button"
            aria-label="Add context"
            @click="toggleMenu"
        >
            <slot name="icon">
                <UiIcon name="Fa6SolidPlus" class="text-stone-gray h-5 w-5" />
            </slot>
        </button>

        <Teleport to="body">
            <!-- Handle click outside -->
            <div v-if="isMenuOpen" class="fixed inset-0 z-40" @click="closeMenu"></div>

            <AnimatePresence>
                <motion.div
                    v-if="isMenuOpen"
                    ref="menuRef"
                    key="attachment-menu"
                    data-add-context-menu
                    :style="{
                        position: 'fixed',
                        top: `${menuPosition.top}px`,
                        left: `${menuPosition.left}px`,
                    }"
                    :initial="{
                        opacity: 0,
                        scale: 0.3,
                        transformOrigin: 'bottom left',
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
                    class="text-stone-gray bg-obsidian/25 border-stone-gray/10 z-50 w-52 rounded-xl border p-1.5 shadow-lg
                        backdrop-blur-lg"
                >
                    <ul class="flex flex-col gap-1">
                        <li class="text-stone-gray/60 px-2 pt-1 text-xs font-semibold">Git</li>
                        <li>
                            <button
                                type="button"
                                class="hover:bg-stone-gray/20 flex w-full cursor-pointer items-center gap-3 rounded-lg px-2 py-1.5 text-sm
                                    font-semibold transition-colors duration-200"
                                @click="handleGitSelect('files')"
                            >
                                <UiIcon name="MdiFileDocumentOutline" class="h-5 w-5" />
                                <span>Add files</span>
                            </button>
                        </li>
                        <li>
                            <button
                                type="button"
                                class="hover:bg-stone-gray/20 flex w-full cursor-pointer items-center gap-3 rounded-lg px-2 py-1.5 text-sm
                                    font-semibold transition-colors duration-200"
                                @click="handleGitSelect('issues')"
                            >
                                <UiIcon name="MdiSourcePull" class="h-5 w-5" />
                                <span>Add PR/issue</span>
                            </button>
                        </li>
                        <li class="text-stone-gray/60 px-2 pt-2 text-xs font-semibold">Files</li>
                        <li>
                            <label
                                class="hover:bg-stone-gray/20 flex w-full cursor-pointer items-center gap-3 rounded-lg px-2 py-1.5 text-sm
                                    font-semibold transition-colors duration-200"
                            >
                                <UiIcon name="UilUpload" class="h-5 w-5" />
                                <span>From device</span>
                                <input
                                    type="file"
                                    multiple
                                    class="hidden"
                                    @change="handleFileChange"
                                />
                            </label>
                        </li>
                        <li>
                            <button
                                class="hover:bg-stone-gray/20 flex w-full cursor-pointer items-center gap-3 rounded-lg px-2 py-1.5 text-sm
                                    font-semibold transition-colors duration-200"
                                type="button"
                                @click="handleCloudSelect"
                            >
                                <UiIcon name="MdiCloudUploadOutline" class="h-5 w-5" />
                                <span>From cloud</span>
                            </button>
                        </li>
                    </ul>
                </motion.div>
            </AnimatePresence>
        </Teleport>
    </div>
</template>

<style scoped></style>
