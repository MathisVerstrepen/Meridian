import { mountSuspended } from '@nuxt/test-utils/runtime';
import { describe, expect, it } from 'vitest';
import WebSearchView from '@/components/ui/chat/utils/toolCallFormatted/WebSearchView.vue';
import type { ToolCallDetail } from '@/types/toolCall';

const createDetail = (
    argumentsValue: Record<string, unknown>,
    result: Record<string, unknown> | unknown[],
): ToolCallDetail => ({
    id: 'detail-id',
    node_id: 'node-id',
    tool_call_id: 'tool-call-id',
    tool_name: 'web_search',
    status: 'completed',
    arguments: argumentsValue,
    result,
    model_context_payload: '',
});

describe('WebSearchView', () => {
    it('renders canonical searches in order with associated results and shared metadata once', async () => {
        const wrapper = await mountSuspended(WebSearchView, {
            props: {
                detail: createDetail(
                    {
                        queries: ['first query', 'second query'],
                        time_range: 'week',
                        language: 'en',
                    },
                    {
                        searches: [
                            {
                                query: 'first query',
                                results: [
                                    {
                                        title: '',
                                        url: 'https://first.example/result',
                                        content: '',
                                    },
                                ],
                            },
                            {
                                results: [
                                    {
                                        title: 'Second result',
                                        url: 'https://second.example/result',
                                        content: 'Second result content',
                                    },
                                ],
                            },
                        ],
                    },
                ),
            },
        });

        try {
            const entries = wrapper.findAll('[data-testid="web-search-entry"]');
            expect(entries).toHaveLength(2);
            expect(entries.map((entry) => entry.attributes('data-search-index'))).toEqual(['0', '1']);
            expect(entries.map((entry) => entry.get('[data-testid="web-search-query"]').text())).toEqual(
                ['"first query"', '"second query"'],
            );
            expect(entries[0]?.get('[data-testid="web-search-result"]').attributes('href')).toBe(
                'https://first.example/result',
            );
            expect(entries[0]?.text()).toContain('first.example');
            expect(entries[0]?.text()).not.toContain('Second result content');
            expect(entries[1]?.get('[data-testid="web-search-result"]').attributes('href')).toBe(
                'https://second.example/result',
            );
            expect(entries[1]?.text()).toContain('Second result content');
            expect(
                entries.map((entry) => entry.get('[data-testid="web-search-result-count"]').text()),
            ).toEqual(['1 result', '1 result']);

            const firstLink = entries[0]?.get('[data-testid="web-search-result"]');
            expect(firstLink?.attributes('target')).toBe('_blank');
            expect(firstLink?.attributes('rel')).toBe('noopener noreferrer');
            expect(firstLink?.get('img').attributes('src')).toBe(
                'https://www.google.com/s2/favicons?domain=first.example&sz=32',
            );
            expect(firstLink?.get('img').attributes('alt')).toBe('first.example');
            expect(wrapper.findAll('[data-testid="web-search-time-range"]')).toHaveLength(1);
            expect(wrapper.get('[data-testid="web-search-time-range"]').text()).toBe('week');
            expect(wrapper.findAll('[data-testid="web-search-language"]')).toHaveLength(1);
            expect(wrapper.get('[data-testid="web-search-language"]').text()).toBe('en');
        } finally {
            wrapper.unmount();
        }
    });

    it('keeps successful results visible beside a query-local partial failure', async () => {
        const wrapper = await mountSuspended(WebSearchView, {
            props: {
                detail: createDetail(
                    { queries: ['working query', 'failed query'] },
                    {
                        searches: [
                            {
                                query: 'working query',
                                results: [
                                    {
                                        title: 'Working result',
                                        url: 'https://working.example/result',
                                        content: 'Available content',
                                    },
                                ],
                            },
                            {
                                query: 'failed query',
                                error: 'Provider rejected this query.',
                            },
                        ],
                    },
                ),
            },
        });

        try {
            const entries = wrapper.findAll('[data-testid="web-search-entry"]');
            expect(entries).toHaveLength(2);
            expect(entries[0]?.get('[data-testid="web-search-result"]').attributes('href')).toBe(
                'https://working.example/result',
            );
            expect(entries[0]?.find('[data-testid="web-search-entry-error"]').exists()).toBe(false);
            expect(entries[1]?.get('[data-testid="web-search-entry-error"] p').text()).toBe(
                'Provider rejected this query.',
            );
            expect(entries[1]?.find('[data-testid="web-search-entry-empty"]').exists()).toBe(false);
            expect(entries[1]?.find('[data-testid="web-search-result"]').exists()).toBe(false);
            expect(wrapper.find('[data-testid="web-search-root-error"]').exists()).toBe(false);
        } finally {
            wrapper.unmount();
        }
    });

    it('renders the aggregate and every ordered local error for an all-failed batch', async () => {
        const wrapper = await mountSuspended(WebSearchView, {
            props: {
                detail: createDetail(
                    { queries: ['first failure', 'second failure'] },
                    {
                        searches: [
                            { query: 'first failure', error: 'First provider error.' },
                            { query: 'second failure', error: 'Second provider error.' },
                        ],
                        error: 'All search operations failed.',
                    },
                ),
            },
        });

        try {
            expect(wrapper.get('[data-testid="web-search-root-error"] p').text()).toBe(
                'All search operations failed.',
            );
            const entries = wrapper.findAll('[data-testid="web-search-entry"]');
            expect(
                entries.map((entry) =>
                    entry.get('[data-testid="web-search-entry-error"] p').text(),
                ),
            ).toEqual(['First provider error.', 'Second provider error.']);
            expect(wrapper.find('[data-testid="web-search-entry-empty"]').exists()).toBe(false);
        } finally {
            wrapper.unmount();
        }
    });

    it('shows a root-only error without an empty-success message', async () => {
        const wrapper = await mountSuspended(WebSearchView, {
            props: {
                detail: createDetail(
                    { queries: ['unavailable query'] },
                    { searches: [], error: 'Search service unavailable.' },
                ),
            },
        });

        try {
            expect(wrapper.get('[data-testid="web-search-root-error"] p').text()).toBe(
                'Search service unavailable.',
            );
            expect(wrapper.find('[data-testid="web-search-entry"]').exists()).toBe(false);
            expect(wrapper.text()).not.toContain('No results returned.');
        } finally {
            wrapper.unmount();
        }
    });

    it('renders an empty state inside its successful query block', async () => {
        const wrapper = await mountSuspended(WebSearchView, {
            props: {
                detail: createDetail(
                    { queries: ['empty query'] },
                    { searches: [{ query: 'empty query', results: [] }] },
                ),
            },
        });

        try {
            const entry = wrapper.get('[data-testid="web-search-entry"]');
            expect(entry.get('[data-testid="web-search-query"]').text()).toBe('"empty query"');
            expect(entry.get('[data-testid="web-search-entry-empty"]').text()).toBe(
                'No results returned.',
            );
            expect(entry.find('[data-testid="web-search-entry-error"]').exists()).toBe(false);
        } finally {
            wrapper.unmount();
        }
    });

    it('retains legacy singular-query and top-level result-array rendering', async () => {
        const wrapper = await mountSuspended(WebSearchView, {
            props: {
                detail: createDetail(
                    { query: 'legacy query', time_range: 'month', language: 'fr' },
                    [
                        {
                            title: 'Legacy result',
                            url: 'https://legacy.example/result',
                            content: 'Legacy content',
                        },
                    ],
                ),
            },
        });

        try {
            const entries = wrapper.findAll('[data-testid="web-search-entry"]');
            expect(entries).toHaveLength(1);
            expect(entries[0]?.get('[data-testid="web-search-query"]').text()).toBe('"legacy query"');
            const link = entries[0]?.get('[data-testid="web-search-result"]');
            expect(link?.attributes('href')).toBe('https://legacy.example/result');
            expect(link?.text()).toContain('Legacy result');
            expect(link?.text()).toContain('Legacy content');
            expect(link?.get('img').attributes('src')).toBe(
                'https://www.google.com/s2/favicons?domain=legacy.example&sz=32',
            );
            expect(wrapper.get('[data-testid="web-search-time-range"]').text()).toBe('month');
            expect(wrapper.get('[data-testid="web-search-language"]').text()).toBe('fr');
        } finally {
            wrapper.unmount();
        }
    });
});
