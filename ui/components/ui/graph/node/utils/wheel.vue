<script lang="ts" setup>
import type { WheelSlot } from '@/types/settings';

const emit = defineEmits(['update:isHovering']);

// --- Props ---
const props = defineProps<{
    nodeId: string;
    options: WheelSlot[];
    isHovering: boolean;
}>();

// --- Local State ---
const isCtrlPressed = ref(false);
const hoveredIndex = ref<number | null>(null);

// --- Composables ---
const graphEvents = useGraphEvents();
const { getBlockByNodeType } = useBlocks();

// --- Computed Properties ---
const filteredOptions = computed(() => {
    return props.options.filter((option) => option.mainBloc);
});

const isMenuVisible = computed(
    () => props.isHovering && isCtrlPressed.value && filteredOptions.value.length > 0,
);

// --- Core Logic Functions ---
// Calculates the angle for each icon based on its index
const getIconAngle = (index: number): number => {
    const totalOptions = filteredOptions.value.length;
    if (totalOptions <= 1) {
        return 0;
    }

    const arcDegrees = 150;
    const angle = (arcDegrees / (totalOptions - 1)) * index - arcDegrees / 2;

    return angle;
};

// Emits the selected option's value.
const handleOptionClick = (option: WheelSlot) => {
    if (!option.mainBloc) return;

    graphEvents.emit('node-create', {
        variant: option.mainBloc,
        fromNodeId: props.nodeId,
        options: option.options,
    });

    emit('update:isHovering', false);
};

const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Control' || e.key === 'Meta') {
        isCtrlPressed.value = true;
    }
};
const handleKeyUp = (e: KeyboardEvent) => {
    if (e.key === 'Control' || e.key === 'Meta') {
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
                    v-for="(option, index) in filteredOptions"
                    :key="option.name"
                    class="absolute -top-3 left-1/2 -translate-x-1/2"
                    :style="{
                        'transform-origin': 'top center',
                        'z-index': hoveredIndex === index ? 10 : 1,
                    }"
                    @mouseover="hoveredIndex = index"
                    @mouseleave="hoveredIndex = null"
                >
                    <div
                        class="transition-transform duration-200"
                        :style="{
                            transform: `rotate(${getIconAngle(index)}deg) translateY(2.25rem)`,
                        }"
                        v-for="mainBloc in [getBlockByNodeType(option.mainBloc)]"
                        v-if="option.mainBloc"
                    >
                        <button
                            v-if="mainBloc"
                            @click="handleOptionClick(option)"
                            :title="option.name"
                            :style="{
                                transform: `rotate(${-getIconAngle(index)}deg)`,
                            }"
                            class="group bg-obsidian shadow-stone-gray/10 focus:ring-ember-glow/80 pointer-events-auto flex h-10 w-10
                                items-center justify-center rounded-full shadow-md transition-all duration-150 hover:scale-110
                                hover:brightness-110 focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-800 focus:outline-none"
                        >
                            <UiIcon
                                :name="mainBloc?.icon"
                                class="h-5 w-5 -translate-y-1 transition-transform duration-150"
                                :style="{
                                    color: mainBloc?.color,
                                }"
                            />
                            <div
                                class="absolute bottom-2 left-1/2 flex h-4 w-full -translate-x-1/2 translate-y-1/2 items-center
                                    justify-center gap-0.5"
                            >
                                <div v-for="wheelOption in option.options" :key="wheelOption">
                                    <template
                                        v-for="optionDef in [getBlockByNodeType(wheelOption)]"
                                    >
                                        <div
                                            v-if="optionDef"
                                            :style="{
                                                backgroundColor: optionDef?.color,
                                            }"
                                            class="h-2 w-2 rounded-full"
                                        ></div>
                                    </template>
                                </div>
                            </div>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </Transition>
</template>

<style scoped></style>
