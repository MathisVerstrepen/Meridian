import { mountSuspended } from '@nuxt/test-utils/runtime';
import { describe, expect, it } from 'vitest';
import FetchedPageGroup from '@/components/ui/chat/utils/fetchedPage.vue';
import WebSearchGroup from '@/components/ui/chat/utils/webSearch.vue';
import type { FetchedPage, WebSearch } from '@/types/webSearch';

const successfulSearches: WebSearch[] = [
    {
        query: 'first query',
        toolCallId: 'search-detail',
        results: [
            {
                title: 'First result',
                link: 'https://first.example/result',
                content: 'First result content',
                favicon: 'https://first.example/favicon.ico',
            },
        ],
    },
    {
        query: 'second query',
        toolCallId: 'search-detail',
        results: [
            {
                title: 'Second result',
                link: 'https://second.example/result',
                content: 'Second result content',
            },
        ],
    },
    {
        query: 'search without details',
        results: [],
    },
];

const successfulPages: FetchedPage[] = [
    {
        url: 'https://first.example/article',
        toolCallId: 'fetch-first',
    },
    {
        url: 'https://second.example/article',
        toolCallId: 'fetch-second',
    },
    {
        url: 'https://third.example/no-details',
    },
];

describe('web tool groups', () => {
    it('shows one search summary pill with ordered overlapping favicons and total pages', async () => {
        const searches: WebSearch[] = [
            {
                query: 'first favicon group',
                results: [
                    {
                        title: 'Alpha result',
                        link: 'https://alpha.example/result',
                        content: 'Alpha',
                        favicon: 'https://icons.example/alpha.ico',
                    },
                    {
                        title: 'Missing favicon',
                        link: 'https://missing.example/result',
                        content: 'Missing',
                    },
                    {
                        title: '',
                        link: 'https://alpha.example/fallback-label',
                        content: 'Duplicate',
                        favicon: 'https://icons.example/alpha.ico',
                    },
                ],
            },
            {
                query: 'second favicon group',
                results: [
                    {
                        title: 'Beta result',
                        link: 'https://beta.example/result',
                        content: 'Beta',
                        favicon: 'https://icons.example/beta.ico',
                    },
                    {
                        title: 'Gamma result',
                        link: 'https://gamma.example/result',
                        content: 'Gamma',
                        favicon: 'https://icons.example/gamma.ico',
                    },
                ],
            },
        ];
        const wrapper = await mountSuspended(WebSearchGroup, {
            props: {
                webSearches: searches,
            },
        });

        try {
            const pills = wrapper.findAll('[data-testid="web-search-summary-pill"]');
            const pill = pills[0];
            const stack = wrapper.get('[data-testid="web-search-summary-favicon-stack"]');
            const favicons = wrapper.findAll('[data-testid="web-search-summary-favicon"]');
            expect(pills).toHaveLength(1);
            expect(pill?.classes()).toEqual(expect.arrayContaining(['rounded-full', 'border']));
            expect(pill?.text()).toBe('5 web pages');
            expect(stack.classes()).toContain('-space-x-1.5');
            expect(favicons).toHaveLength(3);
            expect(favicons.every((favicon) => favicon.classes().includes('rounded-full'))).toBe(
                true,
            );
            expect(favicons.map((favicon) => favicon.attributes('src'))).toEqual([
                'https://icons.example/alpha.ico',
                'https://icons.example/alpha.ico',
                'https://icons.example/beta.ico',
            ]);
            expect(favicons.map((favicon) => favicon.attributes('alt'))).toEqual([
                'Alpha result favicon',
                'https://alpha.example/fallback-label favicon',
                'Beta result favicon',
            ]);
            expect(favicons.map((favicon) => favicon.attributes('title'))).toEqual([
                'Alpha result',
                'https://alpha.example/fallback-label',
                'Beta result',
            ]);
        } finally {
            wrapper.unmount();
        }
    });

    it('uses singular search page text and omits the pill for zero results', async () => {
        const wrapper = await mountSuspended(WebSearchGroup, {
            props: {
                webSearches: [
                    {
                        query: 'single result',
                        results: [
                            {
                                title: 'One',
                                link: 'https://one.example',
                                content: 'One',
                            },
                        ],
                    },
                ],
            },
        });

        try {
            expect(wrapper.get('[data-testid="web-search-summary-pill"]').text()).toBe(
                '1 web page',
            );
            expect(wrapper.find('[data-testid="web-search-summary-favicon-stack"]').exists()).toBe(
                false,
            );

            await wrapper.setProps({
                webSearches: [{ query: 'no results', results: [] }],
            });
            expect(wrapper.find('[data-testid="web-search-summary-pill"]').exists()).toBe(false);
        } finally {
            wrapper.unmount();
        }
    });

    it('shows one fetched-page summary pill with ordered favicons and all pages counted', async () => {
        const pages: FetchedPage[] = [
            { url: 'https://first.example/article' },
            { url: 'not-a-valid-url' },
            { url: 'https://first.example/another-article' },
            { url: 'https://second.example/article' },
            { url: 'https://third.example/article' },
        ];
        const wrapper = await mountSuspended(FetchedPageGroup, {
            props: {
                fetchedPages: pages,
            },
        });

        try {
            const pills = wrapper.findAll('[data-testid="fetched-page-summary-pill"]');
            const pill = pills[0];
            const stack = wrapper.get('[data-testid="fetched-page-summary-favicon-stack"]');
            const favicons = wrapper.findAll('[data-testid="fetched-page-summary-favicon"]');
            expect(pills).toHaveLength(1);
            expect(pill?.classes()).toEqual(expect.arrayContaining(['rounded-full', 'border']));
            expect(pill?.text()).toBe('5 web pages');
            expect(stack.classes()).toContain('-space-x-1.5');
            expect(favicons).toHaveLength(3);
            expect(favicons.every((favicon) => favicon.classes().includes('rounded-full'))).toBe(
                true,
            );
            expect(favicons.map((favicon) => favicon.attributes('src'))).toEqual([
                'https://www.google.com/s2/favicons?domain=first.example&sz=32',
                'https://www.google.com/s2/favicons?domain=first.example&sz=32',
                'https://www.google.com/s2/favicons?domain=second.example&sz=32',
            ]);
            expect(favicons.map((favicon) => favicon.attributes('alt'))).toEqual([
                'first.example favicon',
                'first.example favicon',
                'second.example favicon',
            ]);
            expect(favicons.map((favicon) => favicon.attributes('title'))).toEqual([
                'first.example',
                'first.example',
                'second.example',
            ]);
        } finally {
            wrapper.unmount();
        }
    });

    it('uses singular fetched-page text and omits the pill for zero pages', async () => {
        const wrapper = await mountSuspended(FetchedPageGroup, {
            props: {
                fetchedPages: [{ url: 'invalid-but-still-counted' }],
            },
        });

        try {
            expect(wrapper.get('[data-testid="fetched-page-summary-pill"]').text()).toBe(
                '1 web page',
            );
            expect(
                wrapper.find('[data-testid="fetched-page-summary-favicon-stack"]').exists(),
            ).toBe(false);

            await wrapper.setProps({ fetchedPages: [] });
            expect(wrapper.find('[data-testid="fetched-page-summary-pill"]').exists()).toBe(
                false,
            );
        } finally {
            wrapper.unmount();
        }
    });

    it('groups successful searches in order and supports disclosure keyboard controls', async () => {
        const wrapper = await mountSuspended(WebSearchGroup, {
            props: {
                webSearches: successfulSearches,
            },
        });

        try {
            const button = wrapper.get('[data-testid="web-search-disclosure-button"]');

            expect(wrapper.findAll('[data-testid="web-search-disclosure-button"]')).toHaveLength(1);
            expect(button.attributes('aria-expanded')).toBe('false');
            expect(wrapper.find('[data-testid="web-search-disclosure-panel"]').exists()).toBe(false);

            await button.trigger('keydown', { key: 'Enter' });

            const panel = wrapper.get('[data-testid="web-search-disclosure-panel"]');
            const rows = wrapper.findAll('[data-testid="web-search-row"]');
            expect(button.attributes('aria-expanded')).toBe('true');
            expect(button.attributes('aria-controls')).toBe(panel.attributes('id'));
            expect(rows).toHaveLength(3);
            expect(rows.map((row) => row.attributes('data-search-index'))).toEqual([
                '0',
                '1',
                '2',
            ]);
            expect(panel.text().indexOf('first query')).toBeLessThan(
                panel.text().indexOf('second query'),
            );
            expect(panel.text().indexOf('First result')).toBeLessThan(
                panel.text().indexOf('Second result'),
            );
            expect(wrapper.get('a[href="https://first.example/result"]').attributes()).toMatchObject({
                target: '_blank',
                rel: 'noopener noreferrer',
            });

            const details = wrapper.findAll('[data-testid="web-search-details-button"]');
            expect(details).toHaveLength(2);
            expect(details.map((detail) => detail.attributes('aria-label'))).toEqual([
                "View details for web search 'first query'",
                "View details for web search 'second query'",
            ]);
            await details[0]?.trigger('click');
            await details[1]?.trigger('click');
            expect(wrapper.emitted('open-details')).toEqual([
                ['search-detail'],
                ['search-detail'],
            ]);

            await button.trigger('keydown', { key: ' ' });
            expect(button.attributes('aria-expanded')).toBe('false');
            expect(wrapper.find('[data-testid="web-search-disclosure-panel"]').exists()).toBe(false);
        } finally {
            wrapper.unmount();
        }
    });

    it('starts streaming searches open and preserves a user toggle across prop updates', async () => {
        const streamingSearches: WebSearch[] = [
            {
                query: 'live query',
                results: [],
                streaming: true,
            },
            successfulSearches[0] as WebSearch,
        ];
        const wrapper = await mountSuspended(WebSearchGroup, {
            props: {
                webSearches: streamingSearches,
            },
        });

        try {
            const button = wrapper.get('[data-testid="web-search-disclosure-button"]');
            expect(button.attributes('aria-expanded')).toBe('true');
            expect(button.classes()).toContain('animate-pulse');
            expect(button.text()).toContain('Searching web...');
            expect(wrapper.get('[data-testid="web-search-disclosure-panel"]').text()).toContain(
                'Searching web...',
            );

            await button.trigger('click');
            expect(button.attributes('aria-expanded')).toBe('false');

            await wrapper.setProps({
                webSearches: [
                    {
                        query: 'live query',
                        results: [],
                    },
                    successfulSearches[0] as WebSearch,
                ],
            });
            expect(button.attributes('aria-expanded')).toBe('false');
            expect(button.classes()).not.toContain('animate-pulse');
            expect(button.text()).toContain('Web Search');
        } finally {
            wrapper.unmount();
        }
    });

    it('starts search errors open and preserves the full error text', async () => {
        const errorText = 'Search provider failed with complete diagnostic text';
        const wrapper = await mountSuspended(WebSearchGroup, {
            props: {
                webSearches: [
                    {
                        query: 'failed query',
                        toolCallId: 'failed-search',
                        results: [],
                        error: errorText,
                    },
                ],
            },
        });

        try {
            expect(
                wrapper.get('[data-testid="web-search-disclosure-button"]').attributes(
                    'aria-expanded',
                ),
            ).toBe('true');
            expect(wrapper.get('[data-testid="web-search-row"]').text()).toContain('Search Failed');
            expect(wrapper.get('[data-testid="web-search-disclosure-panel"]').text()).toContain(
                errorText,
            );
        } finally {
            wrapper.unmount();
        }
    });

    it('groups successful fetched pages in order and emits exact detail IDs', async () => {
        const wrapper = await mountSuspended(FetchedPageGroup, {
            props: {
                fetchedPages: successfulPages,
            },
        });

        try {
            const button = wrapper.get('[data-testid="fetched-page-disclosure-button"]');
            expect(wrapper.findAll('[data-testid="fetched-page-disclosure-button"]')).toHaveLength(
                1,
            );
            expect(button.attributes('aria-expanded')).toBe('false');

            await button.trigger('keydown', { key: 'Enter' });

            const panel = wrapper.get('[data-testid="fetched-page-disclosure-panel"]');
            const rows = wrapper.findAll('[data-testid="fetched-page-row"]');
            expect(button.attributes('aria-expanded')).toBe('true');
            expect(button.attributes('aria-controls')).toBe(panel.attributes('id'));
            expect(rows.map((row) => row.attributes('data-fetched-page-index'))).toEqual([
                '0',
                '1',
                '2',
            ]);
            expect(panel.text().indexOf('first.example')).toBeLessThan(
                panel.text().indexOf('second.example'),
            );
            expect(panel.text().indexOf('second.example')).toBeLessThan(
                panel.text().indexOf('third.example'),
            );
            expect(wrapper.get('a[href="https://first.example/article"]').attributes()).toMatchObject(
                {
                    target: '_blank',
                    rel: 'noopener noreferrer',
                },
            );

            const details = wrapper.findAll('[data-testid="fetched-page-details-button"]');
            expect(details).toHaveLength(2);
            expect(details.map((detail) => detail.attributes('aria-label'))).toEqual([
                "View details for fetched page 'https://first.example/article'",
                "View details for fetched page 'https://second.example/article'",
            ]);
            await details[0]?.trigger('click');
            await details[1]?.trigger('click');
            expect(wrapper.emitted('open-details')).toEqual([
                ['fetch-first'],
                ['fetch-second'],
            ]);

            await button.trigger('keydown', { key: ' ' });
            expect(button.attributes('aria-expanded')).toBe('false');
            expect(wrapper.find('[data-testid="fetched-page-disclosure-panel"]').exists()).toBe(
                false,
            );
        } finally {
            wrapper.unmount();
        }
    });

    it('starts fetched-page errors open and keeps the error row presentation', async () => {
        const wrapper = await mountSuspended(FetchedPageGroup, {
            props: {
                fetchedPages: [
                    {
                        url: 'https://failed.example/article',
                        toolCallId: 'failed-fetch',
                        error: 'Fetch failed',
                    },
                ],
            },
        });

        try {
            const button = wrapper.get('[data-testid="fetched-page-disclosure-button"]');
            const row = wrapper.get('[data-testid="fetched-page-row"]');
            expect(button.attributes('aria-expanded')).toBe('true');
            expect(row.text()).toContain('failed.example');
            expect(row.text()).toContain('(Error)');
            expect(row.classes()).toContain('border-red-500/20!');

            await button.trigger('click');
            await wrapper.setProps({
                fetchedPages: [
                    {
                        url: 'https://failed.example/article',
                        toolCallId: 'failed-fetch',
                    },
                ],
            });
            expect(button.attributes('aria-expanded')).toBe('false');
        } finally {
            wrapper.unmount();
        }
    });
});
