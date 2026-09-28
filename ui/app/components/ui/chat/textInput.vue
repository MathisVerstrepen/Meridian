<script lang="ts" setup>
import type { NodeTypeEnum } from '@/types/enums';
import type { ChatInputSubmission } from '@/types/chat';
import type { BlockDefinition } from '@/types/graph';

const emit = defineEmits<{
    (e: 'triggerScroll'): void;
    (e: 'generate', submission: ChatInputSubmission, restoreInput: () => void): void;
    (e: 'goBackToBottom'): void;
    (e: 'cancelStream'): void;
    (e: 'selectNodeType', nodeType: BlockDefinition): void;
}>();

const props = defineProps<{
    isLockedToBottom: boolean;
    isStreaming: boolean;
    isSubmitting?: boolean;
    nodeType: NodeTypeEnum;
    from: 'home' | 'chat';
}>();

// --- Composables ---
const graphEvents = useGraphEvents();
const { isImageAttachment } = useFiles();
const { githubContext, openGithubContext, removeGithubContext } = useChatGithubContext();

// --- Local State ---
const textareaRef = ref<HTMLDivElement | null>(null);
const message = ref<string>('');
const isEmpty = ref(true);
const files = ref<FileSystemObject[]>([]);
const isDraggingOver = ref(false);

const { addFiles, uploads, isUploading, collision, resolveCollision } = useAttachmentUploads(
    (file) => {
        if (!files.value.some((attached) => attached.id === file.id)) files.value.push(file);
    },
);

const imageAttachments = computed(() => files.value.filter(isImageAttachment));
const nonImageAttachments = computed(() => files.value.filter((file) => !isImageAttachment(file)));

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
    if (props.isSubmitting || props.isStreaming || isUploading.value) return;
    const submission: ChatInputSubmission = {
        message: message.value,
        files: [...files.value],
        githubContext: githubContext.value,
    };

    message.value = '';
    files.value = [];
    githubContext.value = null;
    isEmpty.value = true;
    const el = textareaRef.value;
    if (el) el.innerText = '';

    emit('generate', submission, () => {
        // Never replace a newer draft typed while this submission was pending.
        if (message.value || files.value.length || githubContext.value) return;
        message.value = submission.message;
        files.value = submission.files;
        githubContext.value = submission.githubContext;
        isEmpty.value = !submission.message;
        if (textareaRef.value) textareaRef.value.innerText = submission.message;
    });
};

const removeFile = (file: FileSystemObject) => {
    const index = files.value.indexOf(file);
    if (index >= 0) files.value.splice(index, 1);
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

    const clipboardData = event.clipboardData;
    if (!clipboardData) return;

    const imageFiles = Array.from(clipboardData.items)
        .filter((item) => item.kind === 'file' && item.type.startsWith('image/'))
        .map((item) => item.getAsFile())
        .filter((file): file is File => file !== null);

    // Remove formatting from pasted text
    const text = clipboardData.getData('text/plain');
    if (text) {
        document.execCommand('insertText', false, text);

        onInput();

        // After the DOM updates from the paste, scroll the input field to the bottom
        const el = textareaRef.value;
        if (el) {
            nextTick(() => {
                el.scrollTop = el.scrollHeight;
            });
        }
    }

    if (imageFiles.length) {
        void addFiles(imageFiles);
    }
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
    <UiAttachmentCollisionModal
        v-if="collision"
        :collision="collision"
        @resolve="resolveCollision"
    />
    <div class="relative flex h-fit w-full flex-col items-center justify-end">
        <!-- Scroll to Bottom Button -->
        <button
            v-if="!isLockedToBottom"
            type="button"
            aria-label="Scroll to bottom"
            class="bg-stone-gray/20 hover:bg-stone-gray/10 absolute -top-20 z-20 flex h-10 w-10
                items-center justify-center rounded-full text-white shadow-lg backdrop-blur
                transition-all duration-200 ease-in-out hover:-translate-y-1 hover:scale-110
                hover:cursor-pointer"
            @click="emit('goBackToBottom')"
        >
            <UiIcon name="FlowbiteChevronDownOutline" class="h-6 w-6" />
        </button>

        <!-- File attachments -->
        <div
            v-if="files.length > 0 || githubContext"
            data-attachment-grid
            class="bg-obsidian shadow-soft-silk/5 mx-10 grid h-fit w-[calc(80%-3rem)] max-w-268
                grid-cols-1 gap-2 rounded-t-3xl px-2 py-2 shadow-[0_-5px_15px]"
        >
            <ul
                v-if="githubContext"
                data-attachment-row="github"
                class="col-span-1 flex w-full list-none flex-wrap items-center justify-start gap-2"
            >
                <UiChatGithubContextChip :context="githubContext" @remove="removeGithubContext" />
            </ul>
            <ul
                v-if="imageAttachments.length > 0"
                data-attachment-row="images"
                class="col-span-1 flex w-full list-none flex-wrap items-center justify-start gap-2"
            >
                <UiChatAttachmentChipListItem
                    v-for="file in imageAttachments"
                    :key="file.id"
                    :file="file"
                    :remove-files="true"
                    :show-image-preview="true"
                    @remove-file="removeFile(file)"
                />
            </ul>
            <ul
                v-if="nonImageAttachments.length > 0"
                data-attachment-row="files"
                class="col-span-1 flex w-full list-none flex-wrap items-center justify-start gap-2"
            >
                <UiChatAttachmentChipListItem
                    v-for="file in nonImageAttachments"
                    :key="file.id"
                    :file="file"
                    :remove-files="true"
                    @remove-file="removeFile(file)"
                />
            </ul>
        </div>

        <!-- Main input text bar -->
        <div
            class="border-stone-gray/10 flex h-fit max-h-full w-[80%] max-w-280 items-end
                justify-center rounded-3xl border-2 px-2 py-2 backdrop-blur-lg"
            :class="{
                'shadow-soft-silk/5 shadow-[0_-5px_25px]': files.length === 0 && !githubContext,
                'bg-anthracite/25': from === 'home',
                'bg-obsidian/75': from === 'chat',
            }"
        >
            <UiChatAttachmentUploadButton
                :disabled="isUploading"
                @add-files="addFiles"
                @open-cloud-select="openCloudSelect"
                @add-git-context="openGithubContext"
            >
                <template #icon>
                    <UiChatUtilsUploadProgressCircle
                        v-if="isUploading"
                        :uploads="uploads"
                        class="animate-pulse"
                    />
                    <UiIcon v-else name="Fa6SolidPlus" class="text-stone-gray h-5 w-5" />
                </template>
            </UiChatAttachmentUploadButton>

            <div
                ref="textareaRef"
                contenteditable
                class="contenteditable text-soft-silk/80 custom_scroll mx-2 field-sizing-content
                    h-full w-full resize-none overflow-hidden overflow-y-auto rounded-xl border-2
                    border-dashed border-transparent bg-transparent px-1 py-2.5 transition-all
                    duration-200 ease-in-out outline-none"
                data-placeholder="Type your message here..."
                :class="{
                    'show-placeholder': isEmpty,
                    'border-soft-silk/50! border-2': isDraggingOver,
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
                :is-empty="isEmpty || !!isSubmitting"
                :is-uploading="isUploading"
                @send="sendMessage"
                @cancel-stream="emit('cancelStream')"
                @select-node-type="
                    (newType) => {
                        if (!newType) return;
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
