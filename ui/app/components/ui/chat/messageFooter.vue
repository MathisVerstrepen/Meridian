<script lang="ts" setup>
import type { Message } from '@/types/graph';
import { MessageRoleEnum } from '@/types/enums';

const emit = defineEmits(['regenerate', 'edit', 'branch', 'open-node-data', 'toggle-collapse']);

// --- Props ---
defineProps<{
    message: Message;
    isStreaming: boolean;
    isAssistantLastMessage: boolean;
    isUserLastMessage: boolean;
    isCollapsible?: boolean;
    isCollapsed?: boolean;
}>();

// --- Composables ---
const { getTextFromMessage } = useMessage();
const graphEvents = useGraphEvents();
</script>

<template>
    <div class="mt-2 flex items-center justify-between">
        <div v-if="message.role === MessageRoleEnum.assistant" class="flex items-center gap-2">
            <!-- Used Model -->
            <div
                v-if="message.model && message.model.length > 0"
                title="Used model"
                class="dark:border-anthracite border-stone-gray dark:text-stone-gray/50
                    text-stone-gray rounded-lg border px-2 py-1 text-xs font-bold"
            >
                {{ message.model }}
            </div>

            <!-- Usage Data Popover -->
            <UiChatUtilsUsageDataPopover
                v-if="!isStreaming || !isAssistantLastMessage"
                :message="message"
            />
        </div>

        <div
            v-if="!isStreaming || !isAssistantLastMessage"
            class="flex w-fit items-center justify-center rounded-full"
            :class="{
                'bg-obsidian/50': message.role === MessageRoleEnum.user,
                'bg-anthracite/50': message.role === MessageRoleEnum.assistant,
            }"
        >
            <!-- Open Message Node Data Button -->
            <button
                v-if="message.role === MessageRoleEnum.assistant"
                type="button"
                title="Open message node data (or double click on message)"
                class="hover:bg-anthracite text-soft-silk/80 flex items-center justify-center
                    rounded-full px-2 py-1 transition-colors duration-200 ease-in-out
                    hover:cursor-pointer"
                @click="
                    graphEvents.emit('open-node-data', { selectedNodeId: message.node_id || null })
                "
            >
                <UiIcon name="MdiDatabaseOutline" class="h-5 w-5" />
            </button>

            <!-- Copy to Clipboard Button -->
            <UiChatUtilsCopyButton
                :text-to-copy="getTextFromMessage(message)"
                class="h-7 w-9"
                title="Copy response to clipboard"
                :class="{
                    'hover:bg-anthracite/50': message.role === MessageRoleEnum.assistant,
                    'hover:bg-anthracite': message.role === MessageRoleEnum.user,
                }"
            />

            <!-- Branching Button -->
            <button
                v-if="message.role === MessageRoleEnum.assistant && !isAssistantLastMessage"
                type="button"
                title="Create a branch from this response"
                class="hover:bg-anthracite text-soft-silk/80 flex items-center justify-center
                    rounded-full px-2 py-1 transition-colors duration-200 ease-in-out
                    hover:cursor-pointer"
                @click="emit('branch')"
            >
                <UiIcon name="TablerArrowsSplit2" class="h-5 w-5" />
            </button>

            <!-- Regenerate Answer Button -->
            <button
                v-if="message.role === MessageRoleEnum.assistant && isAssistantLastMessage"
                type="button"
                title="Regenerate this response"
                class="hover:bg-anthracite text-soft-silk/80 flex items-center justify-center
                    rounded-full px-2 py-1 transition-colors duration-200 ease-in-out
                    hover:cursor-pointer"
                @click="emit('regenerate')"
            >
                <UiIcon name="MaterialSymbolsRefreshRounded" class="h-5 w-5" />
            </button>

            <!-- Edit Sent Prompt Button -->
            <button
                v-if="message.role === MessageRoleEnum.user && isUserLastMessage && !isStreaming"
                type="button"
                title="Edit this prompt"
                class="hover:bg-anthracite text-soft-silk/80 flex items-center justify-center
                    rounded-full px-2 py-1 transition-colors duration-200 ease-in-out
                    hover:cursor-pointer"
                @click="emit('edit')"
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
                <span class="dot bg-stone-gray/80 h-1 w-1 rounded-full" />
                <span class="dot bg-stone-gray/80 h-1 w-1 rounded-full" />
                <span class="dot bg-stone-gray/80 h-1 w-1 rounded-full" />
            </div>
        </div>

        <button
            v-if="isCollapsible"
            type="button"
            :title="isCollapsed ? 'Show more' : 'Show less'"
            class="hover:bg-obsidian/20 text-soft-silk/80 flex items-center justify-center
                rounded-full px-2 py-1 transition-colors duration-200 ease-in-out
                hover:cursor-pointer"
            @click="emit('toggle-collapse')"
        >
            <UiIcon
                :name="'FlowbiteChevronDownOutline'"
                :class="isCollapsed ? '' : 'rotate-180'"
                class="h-5 w-5"
            />
        </button>
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
