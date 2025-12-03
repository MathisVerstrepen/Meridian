<script lang="ts" setup>
import type { NodeProps } from '@vue-flow/core';
import { NodeResizer } from '@vue-flow/node-resizer';

import type { DataFilePrompt } from '@/types/graph';

const emit = defineEmits(['updateNodeInternals', 'update:deleteNode', 'update:unlinkNode']);

// --- Stores ---
const settingsStore = useSettingsStore();

// --- State from Stores ---
const { blockAttachmentSettings } = storeToRefs(settingsStore);

// --- Composables ---
const { getBlockById } = useBlocks();
const { uploadFile, getRootFolder, getFolderContents, createFolder } = useAPI();
const graphEvents = useGraphEvents();
const { error } = useToast();
const { nodeRef, isVisible } = useNodeVisibility();

// --- Routing ---
const route = useRoute();
const graphId = computed(() => (route.params.id as string) ?? '');

// --- Constants ---
const blockDefinition = getBlockById('primary-prompt-file');

// --- Props ---
const props = defineProps<NodeProps<DataFilePrompt>>();

// --- Local State ---
const isDraggingOver = ref(false);

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

// Start changed code
const addFiles = async (newFiles: FileList) => {
    if (!newFiles) return;

    const root = await getRootFolder();
    let targetId = root.id;

    const defaultFolder = blockAttachmentSettings.value.default_upload_folder;

    if (defaultFolder) {
        try {
            const contents = await getFolderContents(root.id);
            const folder = contents.find((f) => f.name === defaultFolder && f.type === 'folder');

            if (folder) {
                targetId = folder.id;
            } else {
                const newFolder = await createFolder(defaultFolder, root.id);
                targetId = newFolder.id;
            }
        } catch (err) {
            console.warn('Failed to use default upload folder, falling back to root:', err);
        }
    }

    const uploadPromises = Array.from(newFiles).map(async (file) => {
        try {
            const newFile = await uploadFile(file, targetId);
            props.data.files.push(newFile);
        } catch (err) {
            console.error(`Failed to upload file ${file.name}:`, err);
            error(`Failed to upload file ${file.name}. Please try again.`, {
                title: 'Upload Error',
            });
        }
    });

    await Promise.all(uploadPromises);
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
    <NodeResizer
        :is-visible="props.selected"
        :min-width="blockDefinition?.minSize?.width"
        :min-height="blockDefinition?.minSize?.height"
        color="transparent"
        :node-id="props.id"
    />

    <UiGraphNodeUtilsRunToolbar
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
            'shadow-dried-heather-dark !shadow-[0px_0px_15px_3px]': props.selected,
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
                '!border-soft-silk/50': isDraggingOver,
            }"
            @dragover.prevent="isDraggingOver = true"
            @dragleave.prevent="isDraggingOver = false"
            @drop.prevent="handleDrop"
        >
            <UiGraphNodeUtilsFilePromptFileList
                :files="props.data.files"
                @delete-file="deleteFile"
            />

            <div
                class="flex w-full gap-2"
                :class="{
                    'h-full': props.data.files.length === 0,
                }"
            >
                <UiGraphNodeUtilsFilePromptUploadDeviceButton
                    :files="props.data.files"
                    @add-file="(newFiles) => addFiles(newFiles)"
                    @update-node-internals="emit('updateNodeInternals')"
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
    />
</template>

<style scoped></style>
