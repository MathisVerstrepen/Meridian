<script lang="ts" setup>
import { motion } from 'motion-v';
import { useVueFlow, type NodeProps } from '@vue-flow/core';
import { NodeResizer } from '@vue-flow/node-resizer';

const emit = defineEmits(['updateNodeInternals', 'update:deleteNode']);

const props = defineProps<NodeProps>();

const COLORS = [
    ['border-stone-gray/50 bg-stone-gray/10', 'shadow-stone-gray/25'],
    ['bg-red-500/10 border-red-500/20', 'shadow-red-500/25'],
    ['bg-green-500/10 border-green-500/20', 'shadow-green-500/25'],
    ['bg-blue-500/10 border-blue-500/20', 'shadow-blue-500/25'],
    ['bg-yellow-500/10 border-yellow-500/20', 'shadow-yellow-500/25'],
    ['bg-purple-500/10 border-purple-500/20', 'shadow-purple-500/25'],
    ['bg-pink-500/10 border-pink-500/20', 'shadow-pink-500/25'],
    ['bg-indigo-500/10 border-indigo-500/20', 'shadow-indigo-500/25'],
    ['bg-teal-500/10 border-teal-500/20', 'shadow-teal-500/25'],
    ['bg-orange-500/10 border-orange-500/20', 'shadow-orange-500/25'],
    ['border-stone-gray/5 border-stone-gray/10', 'shadow-stone-gray/10'],
];

// --- Composables ---
const graphEvents = useGraphEvents();
const { viewport } = useVueFlow();

// --- Local State ---
const isDraggingOver = ref(false);
const isDragging = ref(false);

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
    if (isDragging.value) {
        isDraggingOver.value = true;
        graphEvents.emit('node-group-hover', {
            nodeId: props.id,
        });
    }
};

const handleMouseLeave = () => {
    if (isDragging.value) {
        isDraggingOver.value = false;
        graphEvents.emit('node-group-hover', null);
    }
};

onMounted(async () => {
    if (!props.data?.color) {
        props.data!.color = COLORS[0];
        emit('updateNodeInternals');
    }

    const unsubscribeDragStart = graphEvents.on('node-drag-start', () => {
        isDragging.value = true;
    });

    const unsubscribeDragEnd = graphEvents.on('node-drag-end', () => {
        isDragging.value = false;
        isDraggingOver.value = false;
    });

    onUnmounted(() => {
        unsubscribeDragStart();
        unsubscribeDragEnd();
    });
});
</script>

<template>
    <NodeResizer :is-visible="true" color="transparent" :node-id="props.id" />

    <div
        v-if="props.data && props.data.color"
        :class="[
            `pointer-events-auto h-full w-full rounded-xl border-2 border-dashed shadow-lg transition-all
            duration-200 ease-in-out ${props.data?.color[0]}`,
            {
                active: isDraggingOver,
                'opacity-50': props.dragging,
                [`${props.data?.color[1]} !shadow-[0px_0px_15px_3px]`]:
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
                contenteditable="true"
                spellcheck="false"
                class="text-soft-silk nodrag absolute bottom-0 left-0 w-full cursor-text bg-transparent text-2xl font-bold
                    focus:outline-none"
                :style="{
                    transform: `scale(${0.75 + 0.25 / viewport.zoom})`,
                    transformOrigin: 'bottom left',
                }"
                @blur="onTitleChange"
                v-html="props.data?.title"
            ></div>
        </div>

        <div
            contenteditable="true"
            spellcheck="false"
            class="text-stone-gray nodrag absolute top-4 left-4 h-fit w-fit max-w-[calc(100%-2rem)] min-w-20
                cursor-text bg-transparent text-sm whitespace-pre-wrap focus:outline-none"
            @blur="onCommentChange"
            v-html="props.data?.comment"
        ></div>

        <AnimatePresence>
            <motion.div
                v-if="props.selected"
                key="run-toolbar"
                :initial="{ opacity: 0, scale: 0, translateY: 25 }"
                :animate="{ opacity: 1, scale: 1, translateY: 0 }"
                :exit="{ opacity: 0, scale: 0, translateY: 25 }"
                class="bg-soft-silk/5 border-soft-silk/20 absolute -top-16 right-0 z-10 flex h-12 origin-bottom-right
                    items-center justify-between gap-1 rounded-2xl border-2 px-2 shadow-lg backdrop-blur-md"
            >
                <div
                    v-for="color in COLORS"
                    :key="color[0]"
                    :class="`h-7 w-7 cursor-pointer rounded-lg border-2 transition-all duration-200 ease-in-out
                        hover:brightness-200 ${color[0]}`"
                    @click="
                        () => {
                            props.data!.color = color;
                            emit('updateNodeInternals');
                        }
                    "
                ></div>
            </motion.div>
        </AnimatePresence>
    </div>
</template>

<style scoped></style>
