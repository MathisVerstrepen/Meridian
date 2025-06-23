<script lang="ts" setup>
import type { File } from '@/types/files';

const emit = defineEmits(['triggerScroll', 'generate', 'goBackToBottom']);

defineProps<{
    isLockedToBottom: boolean;
}>();

// --- Composables ---
const { getFileType } = useFiles();
const { uploadFile } = useAPI();

// --- Local State ---
const textareaRef = ref<HTMLTextAreaElement | null>(null);
const message = ref<string>('');
const isEmpty = ref(true);
const files = ref<File[]>([]);

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

const addFiles = async (newFiles: globalThis.FileList) => {
    if (!newFiles) return;

    const uploadPromises = Array.from(newFiles).map(async (file) => {
        try {
            const id = await uploadFile(file);
            files.value.push({
                id,
                name: file.name,
                size: file.size,
                type: getFileType(file.name),
            } as File);
        } catch (error) {
            console.error(`Failed to upload file ${file.name}:`, error);
        }
    });

    await Promise.all(uploadPromises);
};
</script>

<template>
    <div class="relative mt-6 flex w-full flex-col items-center justify-center">
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
            class="decoration-none bg-obsidian mx-10 flex h-fit w-[calc(80%-3rem)] max-w-[67rem] flex-wrap items-center
                justify-start gap-2 rounded-t-3xl px-2 py-2 shadow"
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
                py-2 shadow"
        >
            <label
                class="bg-stone-gray/10 hover:bg-stone-gray/20 flex h-12 w-12 items-center justify-center rounded-2xl
                    shadow transition duration-200 ease-in-out hover:cursor-pointer"
            >
                <UiIcon name="MajesticonsAttachment" class="text-stone-gray h-6 w-6" />
                <input
                    type="file"
                    multiple
                    class="hidden"
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
                class="contenteditable text-soft-silk/80 field-sizing-content h-fit max-h-full w-full resize-none
                    overflow-hidden overflow-y-auto border-none bg-transparent px-4 py-3 outline-none"
                data-placeholder="Type your message here..."
                :class="{ 'show-placeholder': isEmpty }"
                @input="onInput"
                @keydown.enter.exact.prevent="sendMessage"
                autofocus
            ></div>
            <button
                class="bg-stone-gray hover:bg-stone-gray/80 flex h-12 w-12 items-center justify-center rounded-2xl shadow
                    transition duration-200 ease-in-out hover:cursor-pointer"
                @click="sendMessage"
            >
                <UiIcon name="IconamoonSendFill" class="text-obsidian h-6 w-6" />
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
    left: 1rem;
    top: 0.75rem;
    color: var(--color-soft-silk);
    opacity: 0.6;
    pointer-events: none;
}

.contenteditable:not(.show-placeholder)::before {
    content: none;
}
</style>
