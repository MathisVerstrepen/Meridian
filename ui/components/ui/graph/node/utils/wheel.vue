<script lang="ts" setup>
import type { WheelOption } from '@/types/graph';

const emit = defineEmits(['update:isHovering']);

// --- Props ---
const props = defineProps<{
    nodeId: string;
    options: WheelOption[];
    isHovering: boolean;
}>();

// --- Local State ---
const isCtrlPressed = ref(false);

// --- Composables ---
const graphEvents = useGraphEvents();

// --- Computed Properties ---
const isMenuVisible = computed(
    () => props.isHovering && isCtrlPressed.value && props.options.length > 0,
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
const handleOptionClick = (option: WheelOption) => {
    graphEvents.emit('node-create', {
        variant: option.value,
        fromNodeId: props.nodeId,
    });
    // isHovering.value = false;
    emit('update:isHovering', false);
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
            class="absolute bottom-full left-1/2 z-30 mb-4 -translate-x-1/2 translate-y-[4.5rem]"
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
</template>

<style scoped></style>
