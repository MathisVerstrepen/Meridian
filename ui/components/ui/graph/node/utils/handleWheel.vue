<script lang="ts" setup>
import { Position, Handle } from '@vue-flow/core';

// Shape of an individual option
interface MenuOption {
    icon: string;
    value: string;
    label: string;
}

// --- Props ---
const props = withDefaults(
    defineProps<{
        nodeId: string;
        options: MenuOption[];
    }>(),
    {
        options: () => [],
    },
);

// --- Composables ---
const graphEvents = useGraphEvents();

// --- Local State ---
const isHovering = ref(false);
const isCtrlPressed = ref(false);

// --- Computed Properties ---
const isMenuVisible = computed(
    () => isHovering.value && isCtrlPressed.value && props.options.length > 0,
);

// --- Core Logic Functions ---

// Calculates the angle for each icon based on its index
const getIconAngle = (index: number): number => {
    const totalOptions = props.options.length;
    if (totalOptions <= 1) {
        return 0;
    }

    const arcDegrees = 150;
    const angle = (arcDegrees / (totalOptions - 1)) * index - arcDegrees / 2;

    return angle;
};

// Emits the selected option's value.
const handleOptionClick = (option: MenuOption) => {
    graphEvents.emit('node-create', {
        variant: option.value,
        fromNodeId: props.nodeId,
    });
    isHovering.value = false;
};

const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Control') {
        isCtrlPressed.value = true;
    }
};
const handleKeyUp = (e: KeyboardEvent) => {
    if (e.key === 'Control') {
        isCtrlPressed.value = false;
    }
};

// --- Lifecycle Hooks ---
onMounted(async () => {
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
});

onUnmounted(() => {
    window.removeEventListener('keydown', handleKeyDown);
    window.removeEventListener('keyup', handleKeyUp);
});
</script>

<template>
    <div class="relative" @mouseenter="isHovering = true" @mouseleave="isHovering = false">
        <!-- The Vue Flow Handle -->
        <Handle
            type="source"
            :position="Position.Bottom"
            style="background: #e5ca5b"
            class="handlebottom"
        />

        <!-- Radial Menu -->
        <Transition
            enter-active-class="transition-all duration-200 ease-out"
            enter-from-class="opacity-0 scale-75"
            enter-to-class="opacity-100 scale-100"
            leave-active-class="transition-all duration-150 ease-in"
            leave-from-class="opacity-100 scale-100"
            leave-to-class="opacity-0 scale-75"
        >
            <div
                v-if="isMenuVisible"
                class="absolute bottom-full left-1/2 mb-4 -translate-x-1/2 translate-y-[4.5rem]"
            >
                <div
                    class="bg-obsidian/10 pointer-events-none relative h-14 w-28 rounded-b-full shadow-lg backdrop-blur-sm"
                >
                    <div
                        v-for="(option, index) in options"
                        :key="option.value"
                        class="absolute -top-3 left-1/2 -translate-x-1/2"
                        :style="{ 'transform-origin': 'top center' }"
                    >
                        <div
                            class="transition-transform duration-200"
                            :style="{
                                transform: `rotate(${getIconAngle(index)}deg) translateY(2.25rem)`,
                            }"
                        >
                            <button
                                @click="handleOptionClick(option)"
                                :title="option.label"
                                :style="{ transform: `rotate(${-getIconAngle(index)}deg)` }"
                                class="group bg-obsidian shadow-stone-gray/10 hover:bg-anthracite focus:ring-terracotta-clay
                                    pointer-events-auto flex h-10 w-10 items-center justify-center rounded-full text-white shadow-md
                                    transition-all duration-150 hover:scale-110 focus:ring-2 focus:ring-offset-2
                                    focus:ring-offset-gray-800 focus:outline-none"
                            >
                                <UiIcon
                                    :name="option.icon"
                                    class="h-5 w-5 transition-transform duration-150"
                                />
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </Transition>
    </div>
</template>

<style>
.handlebottom {
    width: 45px !important;
    height: 10px !important;
    border: 0;
    border-radius: 0 0 12px 12px;
    transform: translate(-50%, 100%);
    cursor: crosshair;
}
</style>
