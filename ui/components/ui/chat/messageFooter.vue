<script lang="ts" setup>
import type { Message } from '@/types/graph';
import { MessageRoleEnum, NodeTypeEnum } from '@/types/enums';

const emit = defineEmits(['regenerate', 'edit', 'branch']);

// --- Props ---
const props = defineProps<{
    message: Message;
    isStreaming: boolean;
    isAssistantLastMessage: boolean;
    isUserLastMessage: boolean;
}>();

// --- Composables ---
const { formatMessageCost } = useFormatters();
const { getTextFromMessage } = useMessage();

// --- State ---
const open = ref(false);
const usageDataTotal = computed(() => {
    // For parallelization, we combine usage data from all models
    if (props.message.type === NodeTypeEnum.PARALLELIZATION) {
        const modelsUsageData = props.message.data.map((data: any) => data.usageData);
        const aggregatorUsageData = props.message.usageData;
        const allUsageData = [...modelsUsageData, aggregatorUsageData];

        const filteredUsageData = allUsageData.filter((data) => data !== null);

        // Sum all usage data
        return filteredUsageData.reduce(
            (acc: any, curr: any) => ({
                prompt_tokens: acc.prompt_tokens + curr.prompt_tokens,
                completion_tokens: acc.completion_tokens + curr.completion_tokens,
                total_tokens: acc.total_tokens + curr.total_tokens,
                cost: acc.cost + curr.cost,
            }),
            {
                prompt_tokens: 0,
                completion_tokens: 0,
                total_tokens: 0,
                cost: 0,
            },
        );
    }

    return (
        props.message?.usageData || {
            prompt_tokens: 0,
            completion_tokens: 0,
            total_tokens: 0,
            cost: 0,
        }
    );
});
</script>

<template>
    <div class="mt-2 flex items-center justify-between">
        <div class="flex items-center gap-2" v-if="message.role === MessageRoleEnum.assistant">
            <!-- Used Model -->
            <div
                class="dark:border-anthracite border-stone-gray dark:text-stone-gray/50 text-stone-gray rounded-lg border
                    px-2 py-1 text-xs font-bold"
            >
                {{ message.model }}
            </div>
            <!-- Usage Data Popover -->
            <HeadlessPopover class="relative">
                <HeadlessPopoverButton
                    as="div"
                    class="dark:border-anthracite border-stone-gray dark:text-stone-gray/50 text-stone-gray cursor-pointer
                        rounded-lg border px-2 py-1 text-xs font-bold"
                    @mouseover="open = true"
                    @mouseleave="open = false"
                >
                    {{ formatMessageCost(usageDataTotal.cost) }}
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
                                {{ usageDataTotal.prompt_tokens }}
                            </p>
                            <p class="text-xs">
                                <span class="font-bold">Completion Tokens:</span>
                                {{ usageDataTotal.completion_tokens }}
                            </p>
                            <p class="text-xs">
                                <span class="font-bold">Total Tokens:</span>
                                {{ usageDataTotal.total_tokens }}
                            </p>
                            <p class="text-xs">
                                <span class="font-bold">Cost:</span>
                                {{ formatMessageCost(usageDataTotal.cost) }}
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
            <UiChatUtilsCopyButton
                :text-to-copy="getTextFromMessage(message)"
                class="h-7 w-9"
                :class="{
                    'hover:bg-anthracite/50': message.role === MessageRoleEnum.assistant,
                    'hover:bg-anthracite': message.role === MessageRoleEnum.user,
                }"
            ></UiChatUtilsCopyButton>

            <!-- Branching Button -->
            <button
                @click="emit('branch')"
                type="button"
                aria-label="Regenerate this response"
                class="hover:bg-anthracite text-soft-silk/80 flex items-center justify-center rounded-full px-2 py-1
                    transition-colors duration-200 ease-in-out hover:cursor-pointer"
                v-if="message.role === MessageRoleEnum.assistant && !isAssistantLastMessage"
            >
                <UiIcon name="MingcuteGitMergeLine" class="h-5 w-5" />
            </button>

            <!-- Regenerate Answer Button -->
            <button
                @click="emit('regenerate')"
                type="button"
                aria-label="Regenerate this response"
                class="hover:bg-anthracite text-soft-silk/80 flex items-center justify-center rounded-full px-2 py-1
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
                class="hover:bg-anthracite text-soft-silk/80 flex items-center justify-center rounded-full px-2 py-1
                    transition-colors duration-200 ease-in-out hover:cursor-pointer"
                v-if="message.role === MessageRoleEnum.user && isUserLastMessage && !isStreaming"
            >
                <UiIcon name="MaterialSymbolsEditRounded" class="h-5 w-5" />
            </button>
        </div>

        <div
            v-else-if="
                isStreaming && isAssistantLastMessage && getTextFromMessage(message).length > 0
            "
            class="flex h-4 items-center justify-center px-2"
        >
            <div class="flex items-end gap-1">
                <span class="dot bg-stone-gray/80 h-1 w-1 rounded-full"></span>
                <span class="dot bg-stone-gray/80 h-1 w-1 rounded-full"></span>
                <span class="dot bg-stone-gray/80 h-1 w-1 rounded-full"></span>
            </div>
        </div>
    </div>
</template>

<style scoped>
.dot {
    animation: jump 1.4s infinite ease-in-out;
}

.dot:nth-of-type(2) {
    animation-delay: 0.2s;
}

.dot:nth-of-type(3) {
    animation-delay: 0.4s;
}

@keyframes jump {
    0%,
    80%,
    100% {
        transform: translateY(0);
    }
    40% {
        transform: translateY(-5px);
    }
}
</style>
