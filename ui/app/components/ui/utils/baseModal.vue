<script lang="ts" setup>
import { motion } from 'motion-v';

type ModalSize = 'sm' | 'md' | 'lg' | 'xl' | 'fullscreen';
type ModalPosition = 'fixed' | 'absolute';
type ModalVariant = 'default' | 'danger';

const props = withDefaults(
    defineProps<{
        modelValue: boolean;
        title?: string;
        description?: string;
        icon?: string;
        size?: ModalSize;
        variant?: ModalVariant;
        position?: ModalPosition;
        teleport?: boolean;
        closeOnBackdrop?: boolean;
        closeOnEsc?: boolean;
        showClose?: boolean;
        zIndexClass?: string;
        overlayClass?: string;
        panelClass?: string;
        headerClass?: string;
        bodyClass?: string;
        footerClass?: string;
        labelledBy?: string;
        ariaLabel?: string;
    }>(),
    {
        title: undefined,
        description: undefined,
        icon: undefined,
        size: 'md',
        variant: 'default',
        position: 'fixed',
        teleport: true,
        closeOnBackdrop: true,
        closeOnEsc: true,
        showClose: true,
        zIndexClass: 'z-50',
        overlayClass: '',
        panelClass: '',
        headerClass: '',
        bodyClass: '',
        footerClass: '',
        labelledBy: undefined,
        ariaLabel: undefined,
    },
);

const emit = defineEmits<{
    (e: 'update:modelValue', value: boolean): void;
    (e: 'close'): void;
}>();

const slots = useSlots();

const modalId = `modal-${Math.random().toString(36).slice(2, 10)}`;

const sizeClasses: Record<ModalSize, string> = {
    sm: 'max-w-md',
    md: 'max-w-lg',
    lg: 'max-w-2xl',
    xl: 'max-w-6xl',
    fullscreen: 'max-w-7xl',
};

const hasHeader = computed(() => Boolean(slots.header || props.title || props.description));
const hasFooter = computed(() => Boolean(slots.footer));
const titleId = computed(() => props.labelledBy || `${modalId}-title`);

const overlayClasses = computed(() => [
    props.position,
    'inset-0 flex items-center justify-center p-4 backdrop-blur-md',
    props.zIndexClass,
    props.overlayClass || 'bg-black/60',
]);

const panelClasses = computed(() => [
    'text-soft-silk relative w-full overflow-hidden rounded-2xl border shadow-2xl',
    sizeClasses[props.size],
    'bg-obsidian border-stone-gray/20',
    props.panelClass,
]);

const iconWrapClass = computed(() =>
    props.variant === 'danger' ? 'bg-red-500/10' : 'bg-ember-glow/10',
);

const iconClass = computed(() =>
    props.variant === 'danger' ? 'text-red-400 h-5 w-5' : 'text-ember-glow h-5 w-5',
);

const close = () => {
    emit('update:modelValue', false);
    emit('close');
};

const closeFromBackdrop = () => {
    if (props.closeOnBackdrop) {
        close();
    }
};

const handleKeydown = (event: KeyboardEvent) => {
    if (!props.closeOnEsc || !props.modelValue || event.key !== 'Escape') {
        return;
    }

    close();
};

onMounted(() => {
    window.addEventListener('keydown', handleKeydown);
});

onUnmounted(() => {
    window.removeEventListener('keydown', handleKeydown);
});
</script>

<template>
    <Teleport to="body" :disabled="!teleport">
        <AnimatePresence>
            <motion.div
                v-if="modelValue"
                :initial="{ opacity: 0 }"
                :animate="{ opacity: 1, transition: { duration: 0.2 } }"
                :exit="{ opacity: 0, transition: { duration: 0.15 } }"
                :class="overlayClasses"
                role="dialog"
                aria-modal="true"
                :aria-labelledby="hasHeader ? titleId : undefined"
                :aria-label="!hasHeader ? ariaLabel : undefined"
                @click.self="closeFromBackdrop"
            >
                <motion.div
                    :initial="{ opacity: 0, scale: 0.95, y: 10 }"
                    :animate="{
                        opacity: 1,
                        scale: 1,
                        y: 0,
                        transition: { duration: 0.2, ease: 'easeOut' },
                    }"
                    :exit="{
                        opacity: 0,
                        scale: 0.95,
                        y: 10,
                        transition: { duration: 0.15, ease: 'easeIn' },
                    }"
                    :class="panelClasses"
                >
                    <slot name="panel">
                        <div
                            v-if="hasHeader"
                            class="border-stone-gray/10 flex items-center justify-between gap-4 border-b px-5 py-4"
                            :class="headerClass"
                        >
                            <slot name="header">
                                <div class="flex min-w-0 items-center gap-3">
                                    <div
                                        v-if="icon"
                                        class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl"
                                        :class="iconWrapClass"
                                    >
                                        <UiIcon :name="icon" :class="iconClass" />
                                    </div>
                                    <div class="min-w-0">
                                        <h2
                                            v-if="title"
                                            :id="titleId"
                                            class="text-soft-silk text-lg font-semibold"
                                        >
                                            {{ title }}
                                        </h2>
                                        <p
                                            v-if="description"
                                            class="text-stone-gray/60 mt-1 text-sm leading-relaxed"
                                        >
                                            {{ description }}
                                        </p>
                                    </div>
                                </div>
                            </slot>

                            <button
                                v-if="showClose"
                                type="button"
                                class="text-stone-gray/60 hover:bg-stone-gray/10 hover:text-soft-silk rounded-lg p-2
                                    transition-colors flex items-center justify-center"
                                aria-label="Close modal"
                                @click="close"
                            >
                                <UiIcon name="MaterialSymbolsClose" class="h-5 w-5" />
                            </button>
                        </div>

                        <div :class="bodyClass || 'p-5'">
                            <slot />
                        </div>

                        <div
                            v-if="hasFooter"
                            class="border-stone-gray/10 flex items-center justify-end gap-3 border-t px-5 py-4"
                            :class="footerClass"
                        >
                            <slot name="footer" />
                        </div>
                    </slot>
                </motion.div>
            </motion.div>
        </AnimatePresence>
    </Teleport>
</template>
