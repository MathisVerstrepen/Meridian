<script lang="ts" setup>
import { motion } from 'motion-v';

const emit = defineEmits(['close', 'save']);

defineProps<{
    modelSelectDisabled: boolean;
    isTemporary: boolean;
    isEmpty: boolean;
    isLockedToBottom: boolean;
}>();

const forceHide = ref(false);
const hitAreaRef = ref<HTMLElement | null>(null);

let lastPointer: { x: number; y: number } | null = null;

const updateForceHideFromPoint = (x: number, y: number) => {
    const el = hitAreaRef.value;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const inside = x >= r.left && x <= r.right && y >= r.top && y <= r.bottom;
    if (forceHide.value !== inside) forceHide.value = inside;
};

const onPointerMove = (e: PointerEvent) => {
    lastPointer = { x: e.clientX, y: e.clientY };
    updateForceHideFromPoint(e.clientX, e.clientY);
};

const recomputeFromLastPointer = () => {
    if (lastPointer) updateForceHideFromPoint(lastPointer.x, lastPointer.y);
    else forceHide.value = false;
};

onMounted(() => {
    window.addEventListener('pointermove', onPointerMove, { passive: true });
    window.addEventListener('scroll', recomputeFromLastPointer, { passive: true });
    window.addEventListener('resize', recomputeFromLastPointer);
});

onBeforeUnmount(() => {
    window.removeEventListener('pointermove', onPointerMove);
    window.removeEventListener('scroll', recomputeFromLastPointer);
    window.removeEventListener('resize', recomputeFromLastPointer);
});
</script>

<template>
    <div class="absolute top-6 z-20 h-0 w-full px-10">
        <!-- Invisible Hit Area for Hover Detection -->
        <span
            ref="hitAreaRef"
            class="pointer-events-none absolute -top-6 left-0 h-32 w-full"
        ></span>

        <!-- Chat Header -->
        <AnimatePresence>
            <motion.div
                v-if="isLockedToBottom && !forceHide"
                key="chat-header"
                :initial="{ opacity: 0, y: -25, width: '5rem', height: '2.75rem' }"
                :animate="{
                    opacity: 1,
                    y: 0,
                    width: '11rem',
                    height: '2.75rem',
                    transition: {
                        y: { duration: 0.15 },
                        width: { delay: 0.05, duration: 0.2 },
                        height: { duration: 0.3, ease: 'easeInOut' },
                    },
                }"
                :exit="{
                    opacity: 0,
                    y: -25,
                    width: '5rem',
                    height: '2.75rem',
                    transition: {
                        width: { duration: 0.2 },
                        y: { delay: 0.1, duration: 0.1 },
                        height: { duration: 0.3, ease: 'easeInOut' },
                    },
                }"
                class="bg-anthracite/50 border-soft-silk/10 text-soft-silk/80 flex items-center
                    justify-center space-x-3 justify-self-center overflow-hidden rounded-xl border-2
                    backdrop-blur"
            >
                <UiIcon name="MaterialSymbolsAndroidChat" class="h-5 w-5 shrink-0" />
                <span class="font-outfit shrink-0 text-xl font-bold text-nowrap">Chat View</span>
            </motion.div>
        </AnimatePresence>

        <!-- Close Button -->
        <button
            v-if="!isTemporary"
            class="hover:bg-stone-gray/10 absolute -top-1 right-6 flex h-10 w-10 items-center
                justify-center rounded-full p-1 transition-colors duration-200 ease-in-out
                hover:cursor-pointer"
            @click="emit('close')"
        >
            <UiIcon name="MaterialSymbolsClose" class="text-stone-gray h-6 w-6" />
        </button>

        <!-- Save Button -->
        <button
            v-if="isTemporary && !isEmpty"
            class="hover:bg-obsidian/30 bg-obsidian/20 text-soft-silk/80 absolute -top-1 left-2 flex
                h-10 w-fit items-center justify-center gap-2 rounded-full p-1 px-4 transition-colors
                duration-200 ease-in-out hover:cursor-pointer"
            title="Save Conversation"
            @click="emit('save')"
        >
            <UiIcon name="MdiContentSaveOutline" class="text-stone-gray h-5 w-5" />
            <span class="text-stone-gray text-sm font-medium">Save</span>
        </button>
    </div>
</template>

<style scoped></style>
