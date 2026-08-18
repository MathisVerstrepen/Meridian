import { useNuxtApp } from '#app';
import { mountSuspended } from '@nuxt/test-utils/runtime';
import { flushPromises } from '@vue/test-utils';
import { defineComponent, h, nextTick, ref } from 'vue';
import { describe, expect, it, vi } from 'vitest';
import LinkExtractionView from '@/components/ui/chat/utils/toolCallFormatted/LinkExtractionView.vue';
import type { FetchedPageDetailSelection, ToolCallDetail } from '@/types/toolCall';

const createDetail = (
    argumentsValue: Record<string, JsonValue> | unknown[],
    result: Record<string, JsonValue> | unknown[],
): ToolCallDetail => ({
    id: 'detail-id',
    node_id: 'node-id',
    tool_call_id: 'tool-call-id',
    tool_name: 'fetch_page_content',
    status: 'success',
    arguments: argumentsValue,
    result,
    model_context_payload: '',
});

const selection = (index: number): FetchedPageDetailSelection => ({
    kind: 'fetched-page',
    index,
    url: 'https://duplicate.example/article',
});

describe('LinkExtractionView', () => {
    it('renders only the exact selected duplicate URL occurrence', async () => {
        const wrapper = await mountSuspended(LinkExtractionView, {
            props: {
                detail: createDetail(
                    {
                        urls: [
                            'https://duplicate.example/article',
                            'https://duplicate.example/article',
                        ],
                    },
                    {
                        pages: [
                            {
                                url: 'https://duplicate.example/article',
                                markdown_content: 'FIRST_OCCURRENCE_CONTENT',
                            },
                            {
                                url: 'https://duplicate.example/article',
                                markdown_content: 'SECOND_OCCURRENCE_CONTENT',
                            },
                        ],
                    },
                ),
                fetchedPageSelection: selection(1),
            },
        });

        try {
            await flushPromises();
            expect(wrapper.get('[data-testid="link-extraction-source"]').text()).toContain(
                'https://duplicate.example/article',
            );
            expect(wrapper.get('[data-testid="link-extraction-content"]').text()).toContain(
                'SECOND_OCCURRENCE_CONTENT',
            );
            expect(wrapper.text()).not.toContain('FIRST_OCCURRENCE_CONTENT');
        } finally {
            wrapper.unmount();
        }
    });

    it('retains legacy singular URL and root content aliases', async () => {
        const aliases = [
            ['markdown_content', 'LEGACY_MARKDOWN'],
            ['content', 'LEGACY_CONTENT'],
            ['text', 'LEGACY_TEXT'],
        ] as const;
        const wrapper = await mountSuspended(LinkExtractionView, {
            props: {
                detail: createDetail(
                    { url: 'https://legacy.example/article' },
                    { markdown_content: aliases[0][1] },
                ),
                fetchedPageSelection: selection(99),
            },
        });

        try {
            for (const [alias, content] of aliases) {
                await wrapper.setProps({
                    detail: createDetail(
                        { url: 'https://legacy.example/article' },
                        { [alias]: content },
                    ),
                });
                await flushPromises();
                expect(wrapper.get('[data-testid="link-extraction-source"]').text()).toContain(
                    'legacy.example',
                );
                expect(wrapper.get('[data-testid="link-extraction-content"]').text()).toContain(
                    content,
                );
            }

            await wrapper.setProps({
                detail: createDetail(
                    { url: 'https://legacy.example/article' },
                    { error: 'LEGACY_ROOT_ERROR' },
                ),
            });
            await flushPromises();
            expect(wrapper.find('[data-testid="link-extraction-content"]').exists()).toBe(false);
            expect(wrapper.get('[data-testid="link-extraction-root-error"]').text()).toContain(
                'LEGACY_ROOT_ERROR',
            );
        } finally {
            wrapper.unmount();
        }
    });

    it.each([
        ['missing', null],
        ['negative', selection(-1)],
        ['non-integer', selection(0.5)],
        ['out-of-range', selection(2)],
        ['malformed', { kind: 'fetched-page', index: '1', url: 42 } satisfies unknown],
    ])('does not choose a page for %s canonical selection', async (_label, selected) => {
        const wrapper = await mountSuspended(LinkExtractionView, {
            props: {
                detail: createDetail(
                    { urls: ['https://first.example', 'https://second.example'] },
                    {
                        pages: [
                            { markdown_content: 'FIRST_SHOULD_NOT_RENDER' },
                            { markdown_content: 'SECOND_SHOULD_NOT_RENDER' },
                        ],
                        error: 'ROOT_ERROR_STILL_VISIBLE',
                    },
                ),
                fetchedPageSelection: selected,
            },
        });

        try {
            await flushPromises();
            expect(wrapper.find('[data-testid="link-extraction-source"]').exists()).toBe(false);
            expect(wrapper.find('[data-testid="link-extraction-content"]').exists()).toBe(false);
            expect(wrapper.text()).not.toContain('FIRST_SHOULD_NOT_RENDER');
            expect(wrapper.text()).not.toContain('SECOND_SHOULD_NOT_RENDER');
            expect(wrapper.get('[data-testid="link-extraction-root-error"]').text()).toContain(
                'ROOT_ERROR_STILL_VISIBLE',
            );
        } finally {
            wrapper.unmount();
        }
    });

    it('renders validated selected-page and root errors as separate text', async () => {
        const localError = '<img src=x onerror=LOCAL_ERROR_SENTINEL>';
        const rootError = '<script>ROOT_ERROR_SENTINEL</script>';
        const wrapper = await mountSuspended(LinkExtractionView, {
            props: {
                detail: createDetail(
                    { urls: ['https://failed.example/article'] },
                    {
                        pages: [{ url: 'https://failed.example/article', error: localError }],
                        error: rootError,
                    },
                ),
                fetchedPageSelection: selection(0),
            },
        });

        try {
            const local = wrapper.get('[data-testid="link-extraction-local-error"]');
            const root = wrapper.get('[data-testid="link-extraction-root-error"]');
            expect(local.text()).toContain(localError);
            expect(root.text()).toContain(rootError);
            expect(local.find('img').exists()).toBe(false);
            expect(root.find('script').exists()).toBe(false);
        } finally {
            wrapper.unmount();
        }
    });

    it('ignores malformed canonical pages and non-string errors safely', async () => {
        const wrapper = await mountSuspended(LinkExtractionView, {
            props: {
                detail: createDetail(
                    { urls: ['https://malformed.example/article'] },
                    { pages: [{ markdown_content: { nested: true }, error: { message: 'no' } }] },
                ),
                fetchedPageSelection: selection(0),
            },
        });

        try {
            await flushPromises();
            expect(wrapper.find('[data-testid="link-extraction-content"]').exists()).toBe(false);
            expect(wrapper.find('[data-testid="link-extraction-local-error"]').exists()).toBe(false);
            expect(wrapper.find('[data-testid="link-extraction-root-error"]').exists()).toBe(false);
            expect(wrapper.text()).not.toContain('[object Object]');
        } finally {
            wrapper.unmount();
        }
    });

    it('discards a stale parse when the next selected page has only an error', async () => {
        let resolveFirstParse: ((html: string) => void) | undefined;
        let parseSpy: { mockRestore: () => void } | undefined;
        const selectedIndex = ref(0);
        const detail = createDetail(
            {
                urls: ['https://first.example/article', 'https://second.example/article'],
            },
            {
                pages: [
                    { markdown_content: 'STALE_PENDING_CONTENT' },
                    { error: 'CURRENT_SELECTED_ERROR' },
                ],
            },
        );
        const harness = defineComponent({
            setup() {
                const { $markedWorker } = useNuxtApp();
                parseSpy = vi.spyOn($markedWorker, 'parse').mockImplementationOnce(
                    () =>
                        new Promise<string>((resolve) => {
                            resolveFirstParse = resolve;
                        }),
                );

                return () =>
                    h(LinkExtractionView, {
                        detail,
                        fetchedPageSelection: selection(selectedIndex.value),
                    });
            },
        });
        const wrapper = await mountSuspended(harness);

        try {
            selectedIndex.value = 1;
            await nextTick();
            await flushPromises();
            expect(wrapper.get('[data-testid="link-extraction-local-error"]').text()).toContain(
                'CURRENT_SELECTED_ERROR',
            );
            expect(wrapper.find('[data-testid="link-extraction-content"]').exists()).toBe(false);

            resolveFirstParse?.('<p>STALE_PENDING_CONTENT</p>');
            await flushPromises();
            expect(wrapper.text()).not.toContain('STALE_PENDING_CONTENT');
            expect(wrapper.get('[data-testid="link-extraction-local-error"]').text()).toContain(
                'CURRENT_SELECTED_ERROR',
            );
        } finally {
            parseSpy?.mockRestore();
            wrapper.unmount();
        }
    });
});
