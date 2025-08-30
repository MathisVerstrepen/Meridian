<script lang="ts" setup>
const open = ref(false);

const props = defineProps<{
    direction?: 'left' | 'right';
}>();

const buttonRef = ref<HTMLElement | null>(null);
const panelRef = ref<HTMLElement | null>(null);

const updatePanelPosition = () => {
    if (props.direction === 'left' && buttonRef.value && panelRef.value) {
        const rect = buttonRef.value.getBoundingClientRect();
        panelRef.value.style.left = `${rect.left - 500}px`;
        panelRef.value.style.top = `${rect.top}px`;
    }
};

watch(open, (newVal) => {
    if (newVal && props.direction === 'left') {
        nextTick(() => {
            updatePanelPosition();
        });
    }
});
</script>

<template>
    <HeadlessPopover class="relative">
        <HeadlessPopoverButton
            ref="buttonRef"
            as="div"
            class="flex h-6 w-6 cursor-pointer items-center justify-center"
            @mouseover="open = true"
            @mouseleave="open = false"
        >
            <UiIcon name="MaterialSymbolsInfoRounded" class="text-stone-gray h-4 w-4" />
        </HeadlessPopoverButton>

        <!-- IMPORTANT: When above a context that already has a backdrop-blur, this component backdrop-blur will not work -->
        <HeadlessPopoverPanel
            ref="panelRef"
            static
            class="bg-anthracite/75 text-stone-gray fixed z-30 flex w-[500px] flex-col items-start rounded-lg p-4
                shadow-lg backdrop-blur"
            :class="{
                '-translate-x-[480px]': props.direction === 'right',
            }"
            v-if="open"
        >
            <slot name="default"></slot>
        </HeadlessPopoverPanel>
    </HeadlessPopover>
</template>
