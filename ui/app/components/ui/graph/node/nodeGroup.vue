<script lang="ts" setup>
import { motion } from 'motion-v';
import { useVueFlow, type NodeProps } from '@vue-flow/core';
import { NodeResizer } from '@vue-flow/node-resizer';
import {
    NODE_GROUP_COLORS,
    nodeGroupColorFromIndex,
    type NodeGroupColor,
} from '@/constants/nodeGroup';

const emit = defineEmits(['updateNodeInternals', 'update:deleteNode']);

const props = withDefaults(defineProps<NodeProps & { presetEditor?: boolean }>(), {
    presetEditor: false,
});

// --- Stores ---
const dragStore = useDragStore();

// --- Composables ---
const { viewport } = useVueFlow();

// --- Local State ---
const isDraggingOver = ref(false);
const colorIndex = computed(() =>
    typeof props.data?.colorIndex === 'number' ? props.data.colorIndex : 0,
);
const activeColor = computed<NodeGroupColor>(() => {
    if (props.presetEditor) return nodeGroupColorFromIndex(colorIndex.value);
    return (props.data?.color as NodeGroupColor | undefined) ?? nodeGroupColorFromIndex(0);
});
const usesPlainText = computed(
    () => props.presetEditor || props.data?.contentMode === 'plain',
);

const onTitleChange = (event: Event) => {
    const target = event.target as HTMLElement;
    if (props.data) {
        props.data.title = target.innerText;
    }
};

const onCommentChange = (event: Event) => {
    const target = event.target as HTMLElement;
    if (props.data) {
        props.data.comment = target.innerText;
    }
};

const handleMouseEnter = () => {
    if (dragStore.isGlobalDragging) {
        isDraggingOver.value = true;
    }
};

const handleMouseLeave = () => {
    if (dragStore.isGlobalDragging) {
        isDraggingOver.value = false;
    }
};

const handleShiftSpace = () => {
    document.execCommand('insertText', false, ' ');
};

const selectColor = (index: number, color: NodeGroupColor) => {
    if (!props.data) return;
    if (props.presetEditor) {
        props.data.colorIndex = index;
    } else {
        props.data.color = color;
    }
    emit('updateNodeInternals');
};

watch(
    () => dragStore.isGlobalDragging,
    (newVal) => {
        if (!newVal) {
            isDraggingOver.value = false;
        }
    },
);

onMounted(async () => {
    if (props.presetEditor && typeof props.data?.colorIndex !== 'number') {
        props.data!.colorIndex = 0;
        emit('updateNodeInternals');
    } else if (!props.presetEditor && !props.data?.color) {
        props.data!.color = nodeGroupColorFromIndex(0);
        emit('updateNodeInternals');
    }
});
</script>

<template>
    <NodeResizer :is-visible="props.selected" color="transparent" :node-id="props.id" />

    <div
        v-if="props.data"
        :class="[
            `pointer-events-auto h-full w-full rounded-xl border-2 border-dashed shadow-lg
            transition-all duration-200 ease-in-out ${activeColor[0]}`,
            {
                'opacity-50': props.dragging,
                [`${activeColor[1]} shadow-[0px_0px_15px_3px]!`]:
                    props.selected || isDraggingOver,
            },
        ]"
        @dragover.prevent="isDraggingOver = true"
        @dragleave.prevent="isDraggingOver = false"
        @mouseenter="handleMouseEnter"
        @mouseleave="handleMouseLeave"
    >
        <div class="absolute top-[-40px] left-2 h-8 w-[calc(100%-1rem)]">
            <div
                v-if="usesPlainText"
                contenteditable="true"
                spellcheck="false"
                class="text-soft-silk nodrag absolute bottom-0 left-0 w-full cursor-text
                    bg-transparent text-2xl font-bold focus:outline-none"
                :style="{
                    transform: `scale(${0.75 + 0.25 / viewport.zoom})`,
                    transformOrigin: 'bottom left',
                }"
                @blur="onTitleChange"
                @keydown.space.shift.exact.prevent="handleShiftSpace"
            >{{ props.data?.title }}</div>
            <div
                v-else
                contenteditable="true"
                spellcheck="false"
                class="text-soft-silk nodrag absolute bottom-0 left-0 w-full cursor-text
                    bg-transparent text-2xl font-bold focus:outline-none"
                :style="{
                    transform: `scale(${0.75 + 0.25 / viewport.zoom})`,
                    transformOrigin: 'bottom left',
                }"
                @blur="onTitleChange"
                @keydown.space.shift.exact.prevent="handleShiftSpace"
                v-html="props.data?.title"
            ></div>
        </div>

        <div
            v-if="usesPlainText"
            contenteditable="true"
            spellcheck="false"
            class="text-stone-gray nodrag absolute top-4 left-4 h-fit w-fit max-w-[calc(100%-2rem)]
                min-w-20 cursor-text bg-transparent text-sm whitespace-pre-wrap focus:outline-none"
            @blur="onCommentChange"
            @keydown.space.shift.exact.prevent="handleShiftSpace"
        >{{ props.data?.comment }}</div>
        <div
            v-else
            contenteditable="true"
            spellcheck="false"
            class="text-stone-gray nodrag absolute top-4 left-4 h-fit w-fit max-w-[calc(100%-2rem)]
                min-w-20 cursor-text bg-transparent text-sm whitespace-pre-wrap focus:outline-none"
            @blur="onCommentChange"
            @keydown.space.shift.exact.prevent="handleShiftSpace"
            v-html="props.data?.comment"
        ></div>

        <AnimatePresence>
            <motion.div
                v-if="props.selected"
                key="run-toolbar"
                :initial="{ opacity: 0, scale: 0, translateY: 25 }"
                :animate="{ opacity: 1, scale: 1, translateY: 0 }"
                :exit="{ opacity: 0, scale: 0, translateY: 25 }"
                class="bg-soft-silk/5 border-soft-silk/20 absolute -top-16 right-0 z-10 flex h-12
                    origin-bottom-right items-center justify-between gap-1 rounded-2xl border-2 px-2
                    shadow-lg backdrop-blur-md"
            >
                <div
                    v-for="(color, index) in NODE_GROUP_COLORS"
                    :key="color[0]"
                    :class="`h-7 w-7 cursor-pointer rounded-lg border-2 transition-all duration-200
                        ease-in-out hover:brightness-200 ${color[0]}`"
                    @click="selectColor(index, color)"
                ></div>
            </motion.div>
        </AnimatePresence>
    </div>
</template>

<style scoped></style>
