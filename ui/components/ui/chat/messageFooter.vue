<script lang="ts" setup>
import type { Message } from '@/types/graph';
import { MessageRoleEnum } from '@/types/enums';

const emit = defineEmits(['regenerate', 'edit']);

// --- Props ---
defineProps<{
    message: Message;
    isStreaming: boolean;
    isAssistantLastMessage: boolean;
    isUserLastMessage: boolean;
}>();

// --- Core Logic Functions ---
const copyToClipboard = (text: string) => {
    const regex = /\[THINK\](.*?)\[!THINK\]/gs;
    const cleanedText = text.replace(regex, '');
    navigator.clipboard.writeText(cleanedText);
};
</script>

<template>
    <div class="mt-2 flex items-center justify-between">
        <!-- Used Model -->
        <div
            v-if="
                message.role === MessageRoleEnum.assistant &&
                (!isStreaming || !isAssistantLastMessage)
            "
            class="border-anthracite text-stone-gray/50 rounded-lg border px-2 py-1 text-xs font-bold"
        >
            {{ message.model }}
        </div>

        <div
            v-if="!isStreaming || !isAssistantLastMessage"
            class="flex w-fit items-center justify-center rounded-full"
            :class="{
                'bg-obsidian/50': message.role === MessageRoleEnum.user,
                'bg-anthracite/50': message.role === MessageRoleEnum.assistant,
            }"
        >
            <!-- Copy to Clipboard Button -->
            <button
                @click="copyToClipboard(message.content)"
                type="button"
                aria-label="Copy this response"
                class="text-stone-gray flex items-center justify-center rounded-full px-2 py-1 transition-colors
                    duration-200 ease-in-out hover:cursor-pointer"
                :class="{
                    'hover:bg-anthracite/50': message.role === MessageRoleEnum.user,
                    'hover:bg-anthracite': message.role === MessageRoleEnum.assistant,
                }"
            >
                <UiIcon name="MaterialSymbolsContentCopyOutlineRounded" class="h-5 w-5" />
            </button>

            <!-- Regenerate Answer Button -->
            <button
                @click="emit('regenerate')"
                type="button"
                aria-label="Regenerate this response"
                class="hover:bg-anthracite text-stone-gray flex items-center justify-center rounded-full px-2 py-1
                    transition-colors duration-200 ease-in-out hover:cursor-pointer"
                v-if="message.role === MessageRoleEnum.assistant && isAssistantLastMessage"
            >
                <UiIcon name="MaterialSymbolsRefreshRounded" class="h-5 w-5" />
            </button>

            <!-- Edit Sent Prompt Button -->
            <button
                @click="emit('edit')"
                type="button"
                aria-label="Edit this message"
                class="hover:bg-anthracite text-stone-gray flex items-center justify-center rounded-full px-2 py-1
                    transition-colors duration-200 ease-in-out hover:cursor-pointer"
                v-if="message.role === MessageRoleEnum.user && isUserLastMessage && !isStreaming"
            >
                <UiIcon name="MaterialSymbolsEditRounded" class="h-5 w-5" />
            </button>
        </div>
    </div>
</template>

<style scoped></style>
