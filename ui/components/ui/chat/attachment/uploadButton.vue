<script lang="ts" setup>
import { motion } from 'motion-v';

const emit = defineEmits<{
    (e: 'open-cloud-select'): void;
    (e: 'add-files', files: FileList): void;
}>();

// --- Props ---
const props = defineProps<{
    disabled?: boolean;
}>();

// --- Local state ---
const isMenuOpen = ref(false);
const menuRef = ref(null);

const toggleMenu = () => {
    if (props.disabled) return;
    isMenuOpen.value = !isMenuOpen.value;
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
</script>

<template>
    <div ref="menuRef" class="relative">
        <!-- Button mode -->
        <button
            class="bg-stone-gray/10 hover:bg-stone-gray/20 relative flex h-12 w-12 items-center justify-center
                rounded-2xl shadow transition duration-200 ease-in-out hover:cursor-pointer
                disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="disabled"
            @click="toggleMenu"
        >
            <slot name="icon">
                <UiIcon name="MajesticonsAttachment" class="text-stone-gray h-6 w-6" />
            </slot>
        </button>

        <!-- Handle click outside -->
        <div v-if="isMenuOpen" class="fixed inset-0 z-40" @click="closeMenu"></div>

        <AnimatePresence>
            <motion.div
                v-if="isMenuOpen"
                key="attachment-menu"
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
                class="text-soft-silk/90 bg-obsidian/50 absolute bottom-full z-50 mb-2 w-52 rounded-xl p-1.5 shadow-lg
                    backdrop-blur-xl"
            >
                <ul class="flex flex-col gap-1">
                    <li>
                        <label
                            class="flex w-full cursor-pointer items-center gap-3 rounded-lg px-2 py-1.5 text-sm font-semibold
                                hover:bg-white/10"
                        >
                            <UiIcon name="UilUpload" class="h-5 w-5" />
                            <span>Upload from device</span>
                            <input type="file" multiple class="hidden" @change="handleFileChange" />
                        </label>
                    </li>
                    <li>
                        <button
                            class="flex w-full cursor-pointer items-center gap-3 rounded-lg px-2 py-1.5 text-sm font-semibold
                                hover:bg-white/10"
                            @click="handleCloudSelect"
                        >
                            <UiIcon name="MdiCloudUploadOutline" class="h-5 w-5" />
                            <span>Upload from cloud</span>
                        </button>
                    </li>
                </ul>
            </motion.div>
        </AnimatePresence>
    </div>
</template>

<style scoped></style>
