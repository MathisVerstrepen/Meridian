<script lang="ts" setup>
import { type NodeProps } from '@vue-flow/core';
import { NodeResizer } from '@vue-flow/node-resizer';

import type { File } from '@/types/files';
import type { DataFilePrompt } from '@/types/graph';
import { FileType } from '@/types/enums';

const emit = defineEmits(['updateNodeInternals', 'update:deleteNode']);

// --- Composables ---
const { getBlockById } = useBlocks();
const { uploadFile } = useAPI();
const { formatFileSize } = useFormatters();
const { getFileType } = useFiles();
const { error } = useToast();

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

const addFiles = async (newFiles: FileList) => {
    if (!newFiles) return;

    const uploadPromises = Array.from(newFiles).map(async (file) => {
        try {
            const id = await uploadFile(file);
            props.data.files.push({
                id,
                name: file.name,
                size: file.size,
                type: getFileType(file.name),
            } as File);
        } catch (err) {
            console.error(`Failed to upload file ${file.name}:`, err);
            error(`Failed to upload file ${file.name}. Please try again.`, {
                title: 'Upload Error',
            });
        }
    });

    await Promise.all(uploadPromises);
};
</script>

<template>
    <NodeResizer
        :isVisible="true"
        :minWidth="blockDefinition?.minSize?.width"
        :minHeight="blockDefinition?.minSize?.height"
        color="transparent"
        :nodeId="props.id"
    ></NodeResizer>

    <UiGraphNodeUtilsRunToolbar
        :graphId="graphId"
        :nodeId="props.id"
        :selected="props.selected"
        source="input"
        @update:deleteNode="emit('update:deleteNode', props.id)"
    ></UiGraphNodeUtilsRunToolbar>

    <div
        class="bg-dried-heather border-dried-heather-dark relative flex h-full w-full flex-col rounded-3xl border-2
            p-4 pt-3 text-black shadow-lg transition-all duration-200 ease-in-out"
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
                <span
                    class="dark:text-soft-silk/80 text-anthracite -translate-y-0.5 text-lg font-bold"
                >
                    {{ blockDefinition?.name }}
                </span>
            </label>
        </div>

        <!-- Block Content -->
        <div
            @dragover.prevent="isDraggingOver = true"
            @dragleave.prevent="isDraggingOver = false"
            @drop.prevent="handleDrop"
            class="relative mb-2 flex h-full min-h-0 w-full grow flex-col overflow-y-auto rounded-xl border-2
                border-dashed border-transparent transition-all duration-200 ease-in-out"
            :class="{
                '!border-soft-silk/50': isDraggingOver,
            }"
        >
            <ul v-if="props.data.files.length" class="nodrag nowheel hide-scrollbar space-y-1">
                <li
                    v-for="(file, index) in props.data.files"
                    :key="index"
                    class="group dark:text-soft-silk text-anthracite relative grid w-full grid-cols-[auto_1fr_auto_auto]
                        items-center gap-2 rounded-lg p-2 text-sm transition-colors duration-200"
                >
                    <UiIcon
                        class="h-5 w-5"
                        name="BxBxsFileBlank"
                        v-if="file.type === FileType.Other"
                    />
                    <UiIcon
                        class="h-5 w-5"
                        name="BxBxsFilePdf"
                        v-else-if="file.type === FileType.PDF"
                    />
                    <UiIcon
                        class="h-5 w-5"
                        name="MaterialSymbolsImageRounded"
                        v-else-if="file.type === FileType.Image"
                    />
                    <span
                        class="min-w-0 overflow-hidden text-xs overflow-ellipsis whitespace-nowrap"
                        >{{ file.name }}</span
                    >
                    <span
                        class="dark:text-soft-silk/60 text-anthracite w-12 text-end text-[10px] font-bold"
                    >
                        {{ formatFileSize(file.size) }}
                    </span>

                    <button
                        type="button"
                        @click.stop="deleteFile(index)"
                        class="hover:bg-obsidian/20 absolute h-full w-full cursor-pointer rounded-lg opacity-0 backdrop-blur-xs
                            transition-opacity duration-200 group-hover:opacity-100"
                        aria-label="Supprimer le fichier"
                    >
                        <UiIcon name="MaterialSymbolsDeleteRounded" class="h-4 w-4" />
                    </button>
                </li>
            </ul>

            <div v-else class="flex h-full flex-grow items-center justify-center">
                <span class="text-soft-silk/50 text-sm font-bold">No files uploaded yet.</span>
            </div>
        </div>

        <label
            class="dark:text-soft-silk/80 text-anthracite flex h-10 flex-shrink-0 cursor-pointer items-center
                justify-center rounded-lg bg-[#564961] px-4 py-2 transition-colors duration-200
                hover:bg-[#564961]/60"
        >
            <UiIcon class="h-5 w-5" name="UilUpload" />
            <span class="ml-2 text-sm font-bold">Upload File</span>
            <input
                type="file"
                multiple
                class="hidden"
                @change="
                    async (e) => {
                        const target = e.target as HTMLInputElement;
                        if (target.files) {
                            await addFiles(target.files);
                            emit('updateNodeInternals');
                        }
                    }
                "
            />
        </label>
    </div>

    <UiGraphNodeUtilsHandleAttachment type="source" :id="props.id" />
</template>

<style scoped></style>
