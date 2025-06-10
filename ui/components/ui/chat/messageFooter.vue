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

// --- Composables ---
const { formatMessageCost } = useFormatters();

// --- State ---
const open = ref(false);

// --- Core Logic Functions ---
const copyToClipboard = (text: string) => {
    const regex = /\[THINK\](.*?)\[!THINK\]/gs;
    const cleanedText = text.replace(regex, '');
    navigator.clipboard.writeText(cleanedText);
};
</script>

<template>
    <div class="mt-2 flex items-center justify-between">
        <div
            class="flex items-center gap-2"
            v-if="
                message.role === MessageRoleEnum.assistant &&
                (!isStreaming || !isAssistantLastMessage)
            "
        >
            <!-- Used Model -->
            <div
                class="border-anthracite text-stone-gray/50 rounded-lg border px-2 py-1 text-xs font-bold"
            >
                {{ message.model }}
            </div>
            <!-- Usage Data Popover -->
            <HeadlessPopover class="relative" v-if="message.usageData && message.usageData.cost">
                <HeadlessPopoverButton
                    as="div"
                    class="border-anthracite text-stone-gray/50 cursor-pointer rounded-lg border px-2 py-1 text-xs font-bold"
                    @mouseover="open = true"
                    @mouseleave="open = false"
                >
                    {{ formatMessageCost(message.usageData?.cost) }}
                </HeadlessPopoverButton>

                <div v-if="open">
                    <HeadlessPopoverPanel
                        static
                        class="bg-anthracite/75 text-stone-gray absolute -top-[9.5rem] -left-full z-10 flex w-56 flex-col
                            items-start rounded-lg p-4 shadow-lg backdrop-blur-md"
                    >
                        <div class="flex flex-col gap-2">
                            <p class="text-sm font-bold">Usage Details</p>
                            <p class="text-xs">
                                <span class="font-bold">Prompt Tokens:</span>
                                {{ message.usageData.prompt_tokens }}
                            </p>
                            <p class="text-xs">
                                <span class="font-bold">Completion Tokens:</span>
                                {{ message.usageData.completion_tokens }}
                            </p>
                            <p class="text-xs">
                                <span class="font-bold">Total Tokens:</span>
                                {{ message.usageData.total_tokens }}
                            </p>
                            <p class="text-xs">
                                <span class="font-bold">Cost:</span>
                                {{ formatMessageCost(message.usageData.cost) }}
                            </p>
                        </div>
                    </HeadlessPopoverPanel>
                </div>
            </HeadlessPopover>
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
