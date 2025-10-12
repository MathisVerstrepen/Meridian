<script lang="ts" setup>
const open = ref(false);

const props = defineProps<{
    direction?: 'left' | 'right';
}>();

const buttonRef = ref<HTMLElement | null>(null);
const menuPosition = ref({ top: 0, left: 0 });

const updatePanelPosition = () => {
    if (buttonRef.value) {
        const rect = buttonRef.value.getBoundingClientRect();
        menuPosition.value = {
            top: rect.top + 32,
            left: rect.left,
        };
    }
};

watch(open, (newVal) => {
    if (newVal) {
        nextTick(updatePanelPosition);
    }
});
</script>

<template>
    <HeadlessPopover class="relative">
        <HeadlessPopoverButton
            as="template"
            class="flex h-6 w-6 cursor-pointer items-center justify-center"
            @mouseover="open = true"
            @mouseleave="open = false"
        >
            <button ref="buttonRef">
                <UiIcon name="MaterialSymbolsInfoRounded" class="text-stone-gray h-4 w-4" />
            </button>
        </HeadlessPopoverButton>

        <Teleport to="body">
            <Transition
                enter-active-class="transition duration-150 ease-out"
                enter-from-class="transform scale-95 opacity-0"
                enter-to-class="transform scale-100 opacity-100"
                leave-active-class="transition duration-100 ease-in"
                leave-from-class="transform scale-100 opacity-100"
                leave-to-class="transform scale-95 opacity-0"
            >
                <HeadlessPopoverPanel
                    v-if="open"
                    static
                    class="bg-obsidian/50 text-stone-gray border-stone-gray/10 fixed z-30 flex w-[500px] flex-col items-start
                        rounded-lg border p-4 shadow-lg backdrop-blur-xl"
                    :class="{
                        'origin-top-right -translate-x-[480px]': props.direction === 'right',
                        'origin-top-left': props.direction === 'left',
                    }"
                    :style="{
                        top: `${menuPosition.top}px`,
                        left: `${menuPosition.left}px`,
                    }"
                >
                    <slot name="default" />
                </HeadlessPopoverPanel>
            </Transition>
        </Teleport>
    </HeadlessPopover>
</template>
