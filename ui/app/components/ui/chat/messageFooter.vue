<script lang="ts" setup>
import type { Message } from '@/types/graph';
import { MessageRoleEnum } from '@/types/enums';

const emit = defineEmits(['regenerate', 'edit', 'branch', 'open-node-data', 'toggle-collapse']);

// --- Props ---
const props = defineProps<{
    message: Message;
    isStreaming: boolean;
    isAssistantLastMessage: boolean;
    isUserLastMessage: boolean;
    isCollapsible?: boolean;
    isCollapsed?: boolean;
}>();

// --- Composables ---
const { getTextFromMessage } = useMessage();
const { hasPendingAskUserQuestion } = usePendingToolQuestions();
const graphEvents = useGraphEvents();

const TOOL_BLOCK_PATTERNS = [
    /\[WEB_SEARCH\][\s\S]*?(?:\[!WEB_SEARCH\]|$)/g,
    /<search_query(?:\s+[^>]*)?>([\s\S]*?)<\/search_query>\s*((?:<search_res>\s*Title:\s*.+?\s*URL:\s*.+?\s*Content:\s*[\s\S]+?\s*<\/search_res>\s*)+|<search_error>[\s\S]*?<\/search_error>\s*)?/g,
    /<search_res>\s*Title:\s*.+?\s*URL:\s*.+?\s*Content:\s*[\s\S]+?\s*<\/search_res>/g,
    /<search_error>[\s\S]*?<\/search_error>/g,
    /<fetch_url(?:\s+[^>]*)?>[\s\S]*?<\/fetch_url>(?:\s*<fetch_error>[\s\S]*?<\/fetch_error>)?/g,
    /<fetch_error>[\s\S]*?<\/fetch_error>/g,
    /<executing_code(?:\s+[^>]*)?>[\s\S]*?<\/executing_code>/g,
    /<sandbox_artifact\s+tool_call_id="[^"]+"\s+id="[^"]+"\s+kind="[^"]+"\s+name="[^"]*"\s+path="[^"]*"(?:\s+content_type="[^"]*")?><\/sandbox_artifact>/g,
    /<generating_image(?:\s+[^>]*)?>[\s\S]*?<\/generating_image>/g,
    /<generating_image_error(?:\s+[^>]*)?>[\s\S]*?<\/generating_image_error>/g,
    /<generating_mermaid_diagram(?:\s+[^>]*)?>[\s\S]*?<\/generating_mermaid_diagram>/g,
    /<generating_mermaid_diagram_error(?:\s+[^>]*)?>[\s\S]*?<\/generating_mermaid_diagram_error>/g,
    /<visualising(?:\s+[^>]*)?>[\s\S]*?<\/visualising>/g,
    /<visualising_error(?:\s+[^>]*)?>[\s\S]*?<\/visualising_error>/g,
    /<asking_user(?:\s+[^>]*)?>[\s\S]*?<\/asking_user>/g,
] as const;

const normalizeClipboardWhitespace = (text: string): string => {
    return text
        .replace(/[ \t]+\n/g, '\n')
        .replace(/\n{3,}/g, '\n\n')
        .trim();
};

const stripStandaloneControlMarkers = (text: string): string => {
    return text
        .replace(/\[THINK\]|\[!THINK\]/g, '')
        .replace(/\[WEB_SEARCH\]|\[!WEB_SEARCH\]/g, '')
        .replace(/\[IMAGE_GEN\]|\[!IMAGE_GEN\]/g, '');
};

const getAssistantClipboardText = (message: Message): string => {
    const rawText = getTextFromMessage(message);
    let cleanedText = rawText.replace(/\[THINK\][\s\S]*?\[!THINK\]/g, '');

    for (const pattern of TOOL_BLOCK_PATTERNS) {
        cleanedText = cleanedText.replace(pattern, '');
    }

    cleanedText = cleanedText
        .replace(/\[(.*?)\]\(visualise:\/\/<?[0-9a-f-\s]{36,}>?\)/gi, '')
        .replace(/\[ERROR\]([\s\S]*?)(?:\[!ERROR\]|$)/g, '$1');

    cleanedText = stripStandaloneControlMarkers(cleanedText);

    return normalizeClipboardWhitespace(cleanedText);
};

const getClipboardText = (message: Message): string => {
    if (message.role !== MessageRoleEnum.assistant) {
        return getTextFromMessage(message);
    }

    return getAssistantClipboardText(message);
};

const isAwaitingUser = computed(() => {
    if (props.message.role !== MessageRoleEnum.assistant || !props.isAssistantLastMessage) {
        return false;
    }

    return hasPendingAskUserQuestion(getTextFromMessage(props.message));
});
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
            v-if="!isAwaitingUser && (!isStreaming || !isAssistantLastMessage)"
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
                :text-to-copy="getClipboardText(message)"
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
            v-else-if="isAwaitingUser"
            class="bg-ember-glow/10 text-ember-glow/80 flex w-fit items-center gap-1.5
                rounded-full px-2.5 py-1 text-xs font-bold"
        >
            <UiIcon name="LucideMessageCircleDashed" class="h-4 w-4" />
            <span>Awaiting user</span>
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
