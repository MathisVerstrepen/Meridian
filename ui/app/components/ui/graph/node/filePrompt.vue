<script lang="ts" setup>
import type { NodeProps } from '@vue-flow/core';
import { NodeResizer } from '@vue-flow/node-resizer';

import type { DataFilePrompt } from '@/types/graph';

const emit = defineEmits(['updateNodeInternals', 'update:deleteNode', 'update:unlinkNode']);

// --- Composables ---
const { getBlockById } = useBlocks();
const graphEvents = useGraphEvents();
const { nodeRef, isVisible } = useNodeVisibility();

// --- Routing ---
const route = useRoute();
const graphId = computed(() => firstRouteString(route.params.id) ?? '');

// --- Constants ---
const blockDefinition = getBlockById('primary-prompt-file');

// --- Props ---
const props = withDefaults(defineProps<NodeProps<DataFilePrompt> & { presetEditor?: boolean }>(), {
    presetEditor: false,
});

// --- Local State ---
const isDraggingOver = ref(false);
const { addFiles, isUploading, collision, resolveCollision } = useAttachmentUploads((file) => {
    if (!props.data.files.some((attached) => attached.id === file.id)) {
        props.data.files.push(file);
        emit('updateNodeInternals');
    }
});

// --- Core Logic Functions ---
const deleteFile = (fileIndex: number) => {
    props.data.files.splice(fileIndex, 1);
    emit('updateNodeInternals');
};

const handleDrop = async (event: DragEvent) => {
    isDraggingOver.value = false;
    const files = event.dataTransfer?.files;

    if (files && files.length) {
        await addFiles(files);
    }
};

// --- Lifecycle Hooks ---
onMounted(() => {
    const unsubscribe = graphEvents.on('close-attachment-select', ({ selectedFiles, nodeId }) => {
        if (nodeId === props.id) {
            props.data.files = selectedFiles;
            emit('updateNodeInternals');
        }
    });

    onUnmounted(unsubscribe);
});
</script>

<template>
    <UiAttachmentCollisionModal
        v-if="collision"
        :collision="collision"
        @resolve="resolveCollision"
    />
    <NodeResizer
        :is-visible="props.selected"
        :min-width="blockDefinition?.minSize?.width"
        :min-height="blockDefinition?.minSize?.height"
        color="transparent"
        :node-id="props.id"
    />

    <UiGraphNodeUtilsRunToolbar
        v-if="!props.presetEditor"
        :graph-id="graphId"
        :node-id="props.id"
        :selected="props.selected"
        source="input"
        :in-group="props.parentNodeId !== undefined"
        @update:delete-node="emit('update:deleteNode', props.id)"
        @update:unlink-node="emit('update:unlinkNode', props.id)"
    />

    <div
        ref="nodeRef"
        class="bg-dried-heather border-dried-heather-dark relative flex h-full w-full flex-col
            rounded-3xl border-2 p-4 pt-3 text-black shadow-lg transition-all duration-200
            ease-in-out"
        :class="{
            'opacity-50': props.dragging,
            'shadow-dried-heather-dark shadow-[0px_0px_15px_3px]!': props.selected,
        }"
    >
        <!-- Block Header -->
        <div class="mb-2 flex w-full items-center justify-between">
            <label class="flex grow items-center gap-2">
                <UiIcon
                    :name="blockDefinition?.icon || ''"
                    class="dark:text-soft-silk text-anthracite h-6 w-6 opacity-80"
                />
                <span class="dark:text-soft-silk/80 text-anthracite text-lg font-bold">
                    {{ blockDefinition?.name }}
                </span>
            </label>
        </div>

        <!-- Block Content -->
        <div
            v-if="isVisible"
            class="relative flex h-full min-h-0 w-full grow flex-col gap-2 rounded-xl border-2
                border-dashed border-transparent transition-all duration-200 ease-in-out"
            :class="{
                'border-soft-silk/50!': isDraggingOver,
            }"
            @dragover.prevent="isDraggingOver = true"
            @dragleave.prevent="isDraggingOver = false"
            @drop.prevent="handleDrop"
        >
            <UiGraphNodeUtilsFilePromptFileList
                :files="props.data.files"
                @delete-file="deleteFile"
            />

            <p v-if="isUploading" role="status" class="text-soft-silk text-sm">
                {{ collision ? 'Waiting for attachment choice' : 'Adding attachments…' }}
            </p>

            <div
                class="flex w-full gap-2"
                :class="{
                    'h-full': props.data.files.length === 0,
                }"
            >
                <UiGraphNodeUtilsFilePromptUploadDeviceButton
                    :files="props.data.files"
                    @add-file="(newFiles) => addFiles(newFiles)"
                />

                <UiGraphNodeUtilsFilePromptUploadCloudButton
                    :files="props.data.files"
                    :node-id="props.id"
                    @update-node-internals="emit('updateNodeInternals')"
                />
            </div>
        </div>
    </div>

    <UiGraphNodeUtilsHandleAttachment
        :id="props.id"
        type="source"
        :is-dragging="props.dragging"
        :is-visible="isVisible"
        :show-quick-workflow-wheel="!props.presetEditor"
    />
</template>

<style scoped></style>
