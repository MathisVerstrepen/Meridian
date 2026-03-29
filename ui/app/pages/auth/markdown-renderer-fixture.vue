<script setup lang="ts">
import { MessageContentTypeEnum, MessageRoleEnum, NodeTypeEnum } from '@/types/enums';
import MarkdownRenderer from '@/components/ui/chat/markdownRenderer.vue';
import NodeTypeIndicator from '@/components/ui/chat/nodeTypeIndicator.vue';
import {
    DEFAULT_MARKDOWN_RENDERER_FIXTURE_CASE_KEY,
    MARKDOWN_RENDERER_FIXTURE_CASES,
} from '~~/e2e/fixtures/markdownRendererGoldenCase';

definePageMeta({
    layout: 'blank',
});

if (!import.meta.dev) {
    throw createError({
        statusCode: 404,
        statusMessage: 'Not Found',
    });
}

const isRendered = ref(false);
const route = useRoute();
const caseKey =
    typeof route.query.case === 'string'
        ? route.query.case
        : DEFAULT_MARKDOWN_RENDERER_FIXTURE_CASE_KEY;
const fixtureCase = MARKDOWN_RENDERER_FIXTURE_CASES[caseKey];

if (!fixtureCase) {
    throw createError({
        statusCode: 404,
        statusMessage: 'Unknown markdown renderer fixture case',
    });
}

const message = {
    role: MessageRoleEnum.assistant,
    content: [
        {
            type: MessageContentTypeEnum.TEXT,
            text: fixtureCase.rawMessage,
        },
    ],
    model: 'fixture-model',
    node_id: fixtureCase.nodeId,
    type: NodeTypeEnum.TEXT_TO_TEXT,
    data: {
        reply: '',
    },
    usageData: null,
};
</script>

<template>
    <div
        data-testid="markdown-renderer-fixture-page"
        :data-rendered="isRendered ? 'true' : 'false'"
        :data-case-key="fixtureCase.key"
        class="bg-obsidian min-h-screen p-8"
    >
        <div class="mx-auto flex max-w-5xl flex-col gap-6">
            <div class="text-soft-silk/70 text-sm font-semibold tracking-[0.24em] uppercase">
                Markdown renderer fixture
            </div>

            <div
                class="dark:bg-obsidian bg-soft-silk/75 relative ml-[10%] rounded-xl px-6 py-3
                    backdrop-blur-2xl"
            >
                <NodeTypeIndicator :node-type="message.type" />

                <MarkdownRenderer
                    :message="message"
                    :edit-mode="false"
                    @rendered="isRendered = true"
                    @trigger-scroll="undefined"
                    @visualizer-prompt="undefined"
                />
            </div>
        </div>
    </div>
</template>
