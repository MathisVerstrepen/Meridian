<script lang="ts" setup>
import type { File } from '@/types/files';
import { NodeTypeEnum } from '@/types/enums';

const emit = defineEmits(['triggerScroll', 'generate', 'goBackToBottom', 'cancelStream']);

defineProps<{
    isLockedToBottom: boolean;
    isStreaming: boolean;
    nodeType: NodeTypeEnum;
}>();

// --- Composables ---
const { getFileType } = useFiles();
const { uploadFile } = useAPI();
const { error } = useToast();

// --- Local State ---
const textareaRef = ref<HTMLTextAreaElement | null>(null);
const message = ref<string>('');
const isEmpty = ref(true);
const files = ref<File[]>([]);
const isDraggingOver = ref(false);

type UploadStatus = 'uploading' | 'complete' | 'error';
const uploads = ref<Record<string, { status: UploadStatus }>>({});
const isUploading = computed(() => Object.keys(uploads.value).length > 0);

// --- Core Logic Functions ---
const onInput = () => {
    const el = textareaRef.value;
    if (!el) return;
    emit('triggerScroll');
    message.value = el.innerText.trim();
    isEmpty.value = message.value.length === 0;
};

const sendMessage = async () => {
    emit('generate', message.value, files.value);

    message.value = '';
    files.value = [];
    isEmpty.value = true;
    const el = textareaRef.value;
    if (!el) return;
    el.innerText = '';
};

const handleDrop = async (event: DragEvent) => {
    isDraggingOver.value = false;
    const files = event.dataTransfer?.files;

    if (files && files.length) {
        await addFiles(files);
    }
};

const addFiles = async (newFiles: globalThis.FileList) => {
    if (!newFiles) return;

    const currentUploads: Record<string, { status: UploadStatus }> = {};
    const fileList = Array.from(newFiles);

    fileList.forEach((file, index) => {
        const tempId = `upload-${Date.now()}-${index}`;
        currentUploads[tempId] = { status: 'uploading' };
    });
    uploads.value = { ...uploads.value, ...currentUploads };

    const uploadPromises = fileList.map(async (file, index) => {
        const tempId = Object.keys(currentUploads)[index];
        try {
            const id = await uploadFile(file);
            files.value.push({
                id,
                name: file.name,
                size: file.size,
                type: getFileType(file.name),
            } as File);
            uploads.value[tempId].status = 'complete';
        } catch (err) {
            console.error(`Failed to upload file ${file.name}:`, err);
            error(`Failed to upload file ${file.name}. Please try again.`, {
                title: 'Upload Error',
            });
            uploads.value[tempId].status = 'error';
        }
    });

    await Promise.allSettled(uploadPromises);

    setTimeout(() => {
        const completedIds = Object.keys(currentUploads);
        const remainingUploads = { ...uploads.value };
        completedIds.forEach((id) => {
            delete remainingUploads[id];
        });
        uploads.value = remainingUploads;
    }, 100);
};
</script>

<template>
    <div class="relative flex w-full flex-col items-center justify-center">
        <!-- Scroll to Bottom Button -->
        <button
            v-if="!isLockedToBottom"
            @click="emit('goBackToBottom')"
            type="button"
            aria-label="Scroll to bottom"
            class="bg-stone-gray/20 hover:bg-stone-gray/10 absolute -top-20 z-20 flex h-10 w-10 items-center
                justify-center rounded-full text-white shadow-lg backdrop-blur transition-all duration-200
                ease-in-out hover:-translate-y-1 hover:scale-110 hover:cursor-pointer"
        >
            <UiIcon name="FlowbiteChevronDownOutline" class="h-6 w-6" />
        </button>

        <!-- File attachments -->
        <ul
            class="decoration-none bg-obsidian shadow-stone-gray/10 mx-10 flex h-fit w-[calc(80%-3rem)] max-w-[67rem]
                flex-wrap items-center justify-start gap-2 rounded-t-3xl px-2 py-2 shadow-[0_-5px_15px]"
            v-if="files.length > 0"
        >
            <UiChatAttachmentChip
                v-for="(file, index) in files"
                :file="file"
                :index="index"
                @removeFile="files.splice(index, 1)"
                :removeFiles="true"
            />
        </ul>

        <!-- Main input text bar -->
        <div
            class="bg-obsidian flex h-fit max-h-full w-[80%] max-w-[70rem] items-end justify-center rounded-3xl px-2
                py-2"
            :class="{
                'shadow-stone-gray/10 shadow-[0_-5px_15px]': files.length === 0,
            }"
        >
            <label
                class="bg-stone-gray/10 hover:bg-stone-gray/20 relative flex h-12 w-12 items-center justify-center
                    rounded-2xl shadow transition duration-200 ease-in-out hover:cursor-pointer"
            >
                <UiChatUtilsUploadProgressCircle
                    v-if="isUploading"
                    :uploads="uploads"
                    class="animate-pulse"
                />

                <UiIcon
                    v-if="!isUploading"
                    name="MajesticonsAttachment"
                    class="text-stone-gray h-6 w-6"
                />

                <input
                    type="file"
                    multiple
                    class="hidden"
                    :disabled="isUploading"
                    @change="
                        (e) => {
                            const target = e.target as HTMLInputElement;
                            if (target.files) {
                                addFiles(target.files);
                            }
                        }
                    "
                />
            </label>
            <div
                contenteditable
                ref="textareaRef"
                class="contenteditable text-soft-silk/80 custom_scroll mx-2 field-sizing-content h-full w-full resize-none
                    overflow-hidden overflow-y-auto rounded-xl border-2 border-dashed border-transparent bg-transparent
                    px-1 py-2.5 transition-all duration-200 ease-in-out outline-none"
                data-placeholder="Type your message here..."
                :class="{
                    'show-placeholder': isEmpty,
                    '!border-soft-silk/50 border-2': isDraggingOver,
                }"
                @input="onInput"
                @keydown.enter.exact.prevent="sendMessage"
                @dragover.prevent="isDraggingOver = true"
                @dragleave.prevent="isDraggingOver = false"
                @drop.prevent="handleDrop"
                autofocus
            ></div>
            <button
                v-if="!isStreaming"
                :disabled="isEmpty || isUploading"
                @click="sendMessage"
                class="dark:bg-stone-gray dark:hover:bg-stone-gray/80 bg-soft-silk hover:bg-soft-silk/80 flex h-12 w-12
                    items-center justify-center rounded-2xl shadow transition duration-200 ease-in-out
                    hover:cursor-pointer disabled:opacity-50 disabled:hover:cursor-not-allowed"
            >
                <UiIcon name="IconamoonSendFill" class="text-obsidian h-6 w-6" />
            </button>
            <button
                v-else
                :disabled="nodeType !== NodeTypeEnum.TEXT_TO_TEXT"
                @click="emit('cancelStream')"
                class="dark:bg-stone-gray dark:hover:bg-stone-gray/80 bg-soft-silk hover:bg-soft-silk/80 flex h-12 w-12
                    items-center justify-center rounded-2xl shadow transition duration-200 ease-in-out
                    hover:cursor-pointer disabled:opacity-50 disabled:hover:cursor-not-allowed"
            >
                <UiIcon name="MaterialSymbolsStopRounded" class="h-6 w-6" />
            </button>
        </div>
    </div>
</template>

<style scoped>
.contenteditable {
    position: relative;
}

.contenteditable.show-placeholder::before {
    content: attr(data-placeholder);
    position: absolute;
    left: 0.4rem;
    top: 0.6rem;
    color: var(--color-soft-silk);
    opacity: 0.6;
    pointer-events: none;
}

.contenteditable:not(.show-placeholder)::before {
    content: none;
}
</style>
