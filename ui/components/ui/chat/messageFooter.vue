<script lang="ts" setup>
import type { Message } from '@/types/graph';
import { MessageRoleEnum } from '@/types/enums';

// --- Props ---
defineProps({
    message: {
        type: Object as PropType<Message>,
        required: true,
    },
    index: {
        type: Number,
        required: true,
    },
    isStreaming: {
        type: Boolean,
        required: true,
    },
    regenerate: {
        type: Function as PropType<(index: number) => void>,
        required: true,
    },
});

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
            v-if="message.role === MessageRoleEnum.assistant && !isStreaming"
            class="border-anthracite text-stone-gray/50 rounded-lg border px-2 py-1 text-xs font-bold"
        >
            {{ message.model }}
        </div>

        <!-- Regenerate Button -->
        <div
            v-if="!isStreaming"
            class="flex w-fit items-center justify-center rounded-full"
            :class="{
                'bg-obsidian/50': message.role === MessageRoleEnum.user,
                'bg-anthracite/50': message.role === MessageRoleEnum.assistant,
            }"
        >
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

            <button
                @click="regenerate(index)"
                type="button"
                aria-label="Regenerate this response"
                class="hover:bg-anthracite text-stone-gray flex items-center justify-center rounded-full px-2 py-1
                    transition-colors duration-200 ease-in-out hover:cursor-pointer"
                v-if="message.role === MessageRoleEnum.assistant"
            >
                <UiIcon name="MaterialSymbolsRefreshRounded" class="h-5 w-5" />
            </button>
        </div>
    </div>
</template>

<style scoped></style>
