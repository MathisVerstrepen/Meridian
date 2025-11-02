<script lang="ts" setup>
import type { Message } from '@/types/graph';

const props = defineProps<{
    message: Message;
}>();

const emit = defineEmits(['rendered', 'triggerScroll']);

type ParsedBranch = {
    index: string;
    summary?: string;
    messages?: { role: string; content: string }[];
    rawContent?: string;
};

type ParsedContent = {
    title: string;
    format: 'summary' | 'full' | 'error' | 'unknown';
    branches: ParsedBranch[];
};

const parsedContent = computed<ParsedContent>(() => {
    if (typeof window === 'undefined') {
        return { title: '', format: 'unknown', branches: [] };
    }

    const text = props.message.content[0]?.text || '';
    if (!text) {
        return { title: 'Empty Context', format: 'unknown', branches: [] };
    }

    const parser = new DOMParser();
    const doc = parser.parseFromString(text, 'application/xml');

    const parseError = doc.querySelector('parsererror');
    if (parseError) {
        console.error('XML parsing error:', parseError.textContent);
        return {
            title: 'Merged Context (Parsing Error)',
            format: 'error',
            branches: [{ index: '1', rawContent: text }],
        };
    }

    const title = doc.querySelector('title')?.textContent || 'Merged Context';
    const branchNodes = doc.querySelectorAll('branch');

    if (branchNodes.length === 0) {
        return { title, format: 'unknown', branches: [] };
    }

    const firstBranchHasSummary = branchNodes[0].querySelector('summary');
    const format = firstBranchHasSummary ? 'summary' : 'full';

    const branches = Array.from(branchNodes).map((branchNode) => {
        const index = branchNode.getAttribute('index') || 'N/A';
        if (format === 'summary') {
            return {
                index,
                summary: branchNode.querySelector('summary')?.textContent?.trim() || '',
            };
        } else {
            const messageNodes = branchNode.querySelectorAll('message');
            const messages = Array.from(messageNodes).map((msgNode) => ({
                role: msgNode.getAttribute('role') || 'unknown',
                content: msgNode.querySelector('content')?.textContent?.trim() || '',
            }));
            return {
                index,
                messages,
            };
        }
    });

    return { title, format, branches };
});

onMounted(() => {
    emit('rendered');
    emit('triggerScroll');
});
</script>

<template>
    <HeadlessDisclosure
        v-if="parsedContent.branches.length > 0"
        v-slot="{ open }"
        as="div"
        class="group relative"
    >
        <div
            class="dark:bg-obsidian bg-soft-silk/75 border-soft-silk/10 relative overflow-hidden
                rounded-xl border backdrop-blur-md transition-all duration-300"
            :class="{
                'hover:border-ember-glow/50': !open,
                'border-ember-glow': open,
            }"
        >
            <HeadlessDisclosureButton
                class="flex w-full items-center justify-between p-4 text-left focus:outline-none"
            >
                <div class="flex items-center gap-4">
                    <div class="flex items-center gap-3">
                        <div
                            class="bg-ember-glow/10 text-ember-glow flex h-8 w-8 shrink-0
                                items-center justify-center rounded-lg font-bold"
                        >
                            <UiIcon :name="'TablerArrowMerge'" class="h-5 w-5" />
                        </div>
                        <span class="font-semibold">{{ parsedContent.title }}</span>
                    </div>
                    <span
                        v-if="parsedContent.branches.length > 0"
                        class="text-stone-gray dark:text-soft-silk/60 mr-2 shrink-0 text-sm
                            font-medium"
                    >
                        (Combined from {{ parsedContent.branches.length }} sources)
                    </span>
                </div>

                <UiIcon
                    :name="'FlowbiteChevronDownOutline'"
                    :class="{
                        'rotate-180 transform': open,
                    }"
                    class="h-5 w-5"
                />
            </HeadlessDisclosureButton>

            <HeadlessDisclosurePanel
                class="dark:bg-anthracite/30 hide-scrollbar overflow-y-auto transition-[max-height]
                    duration-300 ease-in-out"
                :class="{
                    'max-h-0': !open,
                    'max-h-[800px]': open,
                }"
            >
                <div
                    class="border-t-stone-gray/10 dark:border-t-anthracite/70 space-y-4 border-t
                        p-4"
                >
                    <div
                        v-for="branch in parsedContent.branches"
                        :key="branch.index"
                        class="dark:bg-anthracite/40 bg-stone-gray/10 rounded-lg p-4"
                    >
                        <div class="flex items-center gap-2 text-sm font-semibold">
                            <span
                                class="bg-ember-glow/10 text-ember-glow-dark dark:text-ember-glow
                                    rounded px-2 py-1"
                            >
                                Branch #{{ branch.index }}
                            </span>
                        </div>
                        <!-- Summary View -->
                        <div
                            v-if="parsedContent.format === 'summary'"
                            class="dark:text-soft-silk/80 mt-1 whitespace-pre-wrap"
                        >
                            {{ branch.summary }}
                        </div>

                        <!-- Full History View -->
                        <div
                            v-else-if="parsedContent.format === 'full'"
                            class="mt-2 space-y-4 text-sm"
                        >
                            <div v-for="(msg, msgIndex) in branch.messages" :key="msgIndex">
                                <span
                                    class="font-bold capitalize"
                                    :class="{
                                        'text-slate-blue': msg.role === 'user',
                                        'text-terracotta-clay': msg.role === 'assistant',
                                    }"
                                >
                                    {{ msg.role }}
                                </span>
                                <div class="dark:text-soft-silk/80 mt-1 whitespace-pre-wrap">
                                    {{ msg.content }}
                                </div>
                            </div>
                        </div>

                        <!-- Error Fallback View -->
                        <div
                            v-else-if="parsedContent.format === 'error'"
                            class="dark:text-soft-silk/80 mt-2 font-mono text-sm
                                whitespace-pre-wrap"
                        >
                            {{ branch.rawContent }}
                        </div>
                    </div>
                </div>
            </HeadlessDisclosurePanel>
        </div>
    </HeadlessDisclosure>
</template>
