<script lang="ts" setup>
import type { NodeTypeEnum } from '@/types/enums';

const emit = defineEmits([
    'triggerScroll',
    'generate',
    'goBackToBottom',
    'cancelStream',
    'selectNodeType',
]);

defineProps<{
    isLockedToBottom: boolean;
    isStreaming: boolean;
    nodeType: NodeTypeEnum;
}>();

// --- Composables ---
const { uploadFile, getRootFolder } = useAPI();
const { error } = useToast();
const graphEvents = useGraphEvents();

// --- Local State ---
const textareaRef = ref<HTMLDivElement | null>(null);
const message = ref<string>('');
const isEmpty = ref(true);
const files = ref<FileSystemObject[]>([]);
const isDraggingOver = ref(false);

type UploadStatus = 'uploading' | 'complete' | 'error';
const uploads = ref<Record<string, { status: UploadStatus }>>({});
const isUploading = computed(() => Object.keys(uploads.value).length > 0);

// --- Core Logic Functions ---
const handleInputWheel = (event: WheelEvent) => {
    const el = textareaRef.value;
    if (!el) return;

    const { scrollTop, scrollHeight, clientHeight } = el;
    const isAtTop = scrollTop <= 0;
    const isAtBottom = scrollTop + clientHeight >= scrollHeight - 1;

    const isScrollingUp = event.deltaY < 0;
    const isScrollingDown = event.deltaY > 0;

    if ((isScrollingUp && !isAtTop) || (isScrollingDown && !isAtBottom)) {
        event.stopPropagation();
    }
};

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

const handlePaste = (event: ClipboardEvent) => {
    event.preventDefault();

    // Remove formatting from pasted text
    const text = event.clipboardData?.getData('text/plain');
    if (!text) return;

    document.execCommand('insertText', false, text);

    onInput();

    // After the DOM updates from the paste, scroll the input field to the bottom
    const el = textareaRef.value;
    if (el) {
        nextTick(() => {
            el.scrollTop = el.scrollHeight;
        });
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

    const root = await getRootFolder();

    const uploadPromises = fileList.map(async (file, index) => {
        const tempId = Object.keys(currentUploads)[index];
        try {
            const newFile = await uploadFile(file, root.id);
            files.value.push(newFile);
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
        let remainingUploads = { ...uploads.value };
        completedIds.forEach((id) => {
            remainingUploads = Object.fromEntries(
                Object.entries(remainingUploads).filter(([key]) => key !== id),
            );
        });
        uploads.value = remainingUploads;
    }, 100);
};

const handleShiftSpace = () => {
    document.execCommand('insertText', false, ' ');
    onInput();
};

const openCloudSelect = () => {
    graphEvents.emit('open-attachment-select', {
        nodeId: null,
        selectedFiles: files.value,
    });
};

onMounted(() => {
    const unsubscribe = graphEvents.on(
        'close-attachment-select',
        ({ selectedFiles }: { selectedFiles: FileSystemObject[] }) => {
            if (selectedFiles) {
                files.value = selectedFiles;
            }
        },
    );

    onUnmounted(unsubscribe);
});
</script>

<template>
    <div class="relative flex h-fit w-full flex-col items-center justify-end">
        <!-- Scroll to Bottom Button -->
        <button
            v-if="!isLockedToBottom"
            type="button"
            aria-label="Scroll to bottom"
            class="bg-stone-gray/20 hover:bg-stone-gray/10 absolute -top-20 z-20 flex h-10 w-10 items-center
                justify-center rounded-full text-white shadow-lg backdrop-blur transition-all duration-200
                ease-in-out hover:-translate-y-1 hover:scale-110 hover:cursor-pointer"
            @click="emit('goBackToBottom')"
        >
            <UiIcon name="FlowbiteChevronDownOutline" class="h-6 w-6" />
        </button>

        <!-- File attachments -->
        <ul
            v-if="files.length > 0"
            class="decoration-none bg-obsidian shadow-stone-gray/5 mx-10 flex h-fit w-[calc(80%-3rem)] max-w-[67rem]
                flex-wrap items-center justify-start gap-2 rounded-t-3xl px-2 py-2 shadow-[0_-5px_15px]"
        >
            <UiChatAttachmentChipListItem
                v-for="(file, index) in files"
                :key="file.id"
                :file="file"
                :remove-files="true"
                @remove-file="files.splice(index, 1)"
            />
        </ul>

        <!-- Main input text bar -->
        <div
            class="bg-obsidian flex h-fit max-h-full w-[80%] max-w-[70rem] items-end justify-center rounded-3xl px-2
                py-2"
            :class="{
                'shadow-stone-gray/5 shadow-[0_-5px_15px]': files.length === 0,
            }"
        >
            <UiChatAttachmentUploadButton
                :disabled="isUploading"
                @add-files="addFiles"
                @open-cloud-select="openCloudSelect"
            >
                <template #icon>
                    <UiChatUtilsUploadProgressCircle
                        v-if="isUploading"
                        :uploads="uploads"
                        class="animate-pulse"
                    />
                    <UiIcon v-else name="MajesticonsAttachment" class="text-stone-gray h-6 w-6" />
                </template>
            </UiChatAttachmentUploadButton>

            <div
                ref="textareaRef"
                contenteditable
                class="contenteditable text-soft-silk/80 custom_scroll mx-2 field-sizing-content h-full w-full resize-none
                    overflow-hidden overflow-y-auto rounded-xl border-2 border-dashed border-transparent bg-transparent
                    px-1 py-2.5 transition-all duration-200 ease-in-out outline-none"
                data-placeholder="Type your message here..."
                :class="{
                    'show-placeholder': isEmpty,
                    '!border-soft-silk/50 border-2': isDraggingOver,
                }"
                autofocus
                @input="onInput"
                @wheel.passive="handleInputWheel"
                @keydown.enter.exact.prevent="sendMessage"
                @keydown.space.shift.exact.prevent="handleShiftSpace"
                @dragover.prevent="isDraggingOver = true"
                @dragleave.prevent="isDraggingOver = false"
                @drop.prevent="handleDrop"
                @paste="handlePaste"
            />

            <UiChatUtilsSendChatButton
                :is-streaming="isStreaming"
                :is-empty="isEmpty"
                :is-uploading="isUploading"
                @send="sendMessage"
                @cancel-stream="emit('cancelStream')"
                @select-node-type="
                    (newType) => {
                        emit('selectNodeType', newType);
                    }
                "
            />
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
