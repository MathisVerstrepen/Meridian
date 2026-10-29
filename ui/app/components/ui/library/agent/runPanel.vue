<script setup lang="ts">
import type { AgentRun } from '@/types/agent';
import type { Message } from '@/types/graph';
import { MessageContentTypeEnum, MessageRoleEnum, NodeTypeEnum } from '@/types/enums';

const props = defineProps<{ run: AgentRun; nodeId: string }>();
const scroller = ref<HTMLElement | null>(null);
const { scrollToBottom, triggerScroll, handleScroll } = useChatScroll(scroller);
const message = computed<Message>(() => ({
    role: MessageRoleEnum.assistant,
    type: NodeTypeEnum.AGENT,
    model: props.run.name,
    node_id: props.nodeId,
    data: null,
    usageData: null,
    content: [{ type: MessageContentTypeEnum.TEXT, text: props.run.result }],
}));
const followOutput = async () => {
    await nextTick();
    triggerScroll();
};
onMounted(async () => {
    await nextTick();
    scrollToBottom();
});
watch(() => [props.run.result, props.run.status, props.run.pending_tool_call_id], followOutput, {
    flush: 'post',
});
</script>

<template>
    <div
        ref="scroller"
        data-testid="subagent-output-scroll"
        role="region"
        :aria-label="`${props.run.name} subagent output`"
        tabindex="0"
        class="custom_scroll small_scrollbar nowheel max-h-[min(60vh,32rem)] min-w-0 flex-1
            space-y-3 overflow-y-auto overscroll-contain pr-3 pb-2"
        @scroll="handleScroll"
    >
        <p class="text-stone-gray text-xs">
            @{{ props.run.handle
            }}<template v-if="props.run.version !== null">
                · Version {{ props.run.version }}</template
            >
        </p>
        <p v-if="props.run.instructions" class="text-sm wrap-break-word whitespace-pre-wrap">
            <span class="font-semibold">Task:</span> {{ props.run.instructions }}
        </p>
        <UiChatMarkdownRenderer
            :message="message"
            :edit-mode="false"
            :is-streaming="props.run.status === 'running'"
            @rendered="followOutput"
            @trigger-scroll="followOutput"
        />
        <UiChatUtilsToolQuestionCard
            v-if="
                props.run.pending_tool_call_id &&
                !props.run.result.includes(props.run.pending_tool_call_id)
            "
            :tool-call-id="props.run.pending_tool_call_id"
        />
        <p v-if="props.run.error" role="alert" class="text-sm text-red-500">
            {{ props.run.error }}
        </p>
    </div>
</template>
