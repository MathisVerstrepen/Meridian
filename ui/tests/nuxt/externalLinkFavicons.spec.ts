import { describe, expect, it } from 'vitest';
import {
    buildExternalLinkFaviconUrl,
    decorateExternalLinkFavicons,
} from '@/utils/externalLinkFavicons';

const createRoot = (html: string): HTMLDivElement => {
    const root = document.createElement('div');
    root.innerHTML = html;
    return root;
};

describe('decorateExternalLinkFavicons', () => {
    it('prepends a decorative favicon while preserving the anchor and its existing content', () => {
        const root = createRoot(
            '<a href="https://news.example/story?private=1#section" title="Story" '
            + 'target="_blank" rel="noopener" class="source">Read <strong>News</strong></a>',
        );
        const anchor = root.querySelector('a');
        const originalText = anchor?.firstChild;
        const originalStrong = anchor?.querySelector('strong');

        decorateExternalLinkFavicons(root);

        const decoratedAnchor = root.querySelector('a');
        const favicon = decoratedAnchor?.querySelector<HTMLImageElement>(
            'img[data-external-link-favicon]',
        );
        expect(decoratedAnchor).toBe(anchor);
        expect(decoratedAnchor?.getAttribute('href')).toBe(
            'https://news.example/story?private=1#section',
        );
        expect(decoratedAnchor?.getAttribute('title')).toBe('Story');
        expect(decoratedAnchor?.getAttribute('target')).toBe('_blank');
        expect(decoratedAnchor?.getAttribute('rel')).toBe('noopener');
        expect(decoratedAnchor?.classList.contains('source')).toBe(true);
        expect(decoratedAnchor?.classList.contains('whitespace-nowrap')).toBe(true);
        expect(decoratedAnchor?.childNodes[1]).toBe(originalText);
        expect(decoratedAnchor?.querySelector('strong')).toBe(originalStrong);
        expect(decoratedAnchor?.textContent).toBe('Read News');
        expect(favicon?.src).toBe(buildExternalLinkFaviconUrl(anchor?.getAttribute('href') ?? ''));
        expect(favicon?.getAttribute('alt')).toBe('');
        expect(favicon?.getAttribute('aria-hidden')).toBe('true');
        expect(favicon?.getAttribute('loading')).toBe('lazy');
        expect(favicon?.getAttribute('decoding')).toBe('async');
        expect(favicon?.getAttribute('referrerpolicy')).toBe('no-referrer');
        expect(favicon?.className).toBe(
            'not-prose me-1 inline-block size-4 align-text-bottom rounded-sm',
        );
        expect(decoratedAnchor?.firstElementChild).toBe(favicon);
    });

    it('decorates autolink-shaped and mixed-content anchors with visible text', () => {
        const root = createRoot(`
            <a href="https://auto.example/path">https://auto.example/path</a>
            <a href="http://mixed.example"><img src="preview.png" alt=""> Mixed source</a>
        `);

        decorateExternalLinkFavicons(root);

        expect(root.querySelectorAll('[data-external-link-favicon]')).toHaveLength(2);
        expect(root.querySelectorAll('a.whitespace-nowrap')).toHaveLength(2);
        expect(root.querySelector('a[href="http://mixed.example"]')?.textContent?.trim()).toBe(
            'Mixed source',
        );
    });

    it('skips non-http, malformed, image-only, no-text, and code-only cases', () => {
        const root = createRoot(`
            <a href="/relative">Relative</a>
            <a href="//protocol.example/path">Protocol relative</a>
            <a href="#fragment">Fragment</a>
            <a href="mailto:reader@example.com">Mail</a>
            <a href="tel:+15551234567">Phone</a>
            <a href="javascript:void(0)">Script</a>
            <a href="data:text/plain,hello">Data</a>
            <a href="not a url">Malformed</a>
            <a href="https://image.example"><img src="preview.png" alt="Preview"></a>
            <a href="https://empty.example">   </a>
            <code>https://code.example</code>
        `);

        decorateExternalLinkFavicons(root);

        expect(root.querySelectorAll('[data-external-link-favicon]')).toHaveLength(0);
        expect(root.querySelectorAll('a.whitespace-nowrap')).toHaveLength(0);
    });

    it('is idempotent and respects an existing descendant marker', () => {
        const root = createRoot(`
            <a href="https://first.example">First</a>
            <a href="https://marked.example">
                <span data-external-link-favicon></span>Marked
            </a>
        `);

        decorateExternalLinkFavicons(root);
        decorateExternalLinkFavicons(root);

        expect(
            root.querySelectorAll(
                'a[href="https://first.example"] img[data-external-link-favicon]',
            ),
        ).toHaveLength(1);
        expect(
            root.querySelectorAll('a[href="https://marked.example"] img'),
        ).toHaveLength(0);
        expect(root.querySelectorAll('[data-external-link-favicon]')).toHaveLength(2);
        for (const anchor of root.querySelectorAll('a')) {
            expect(anchor.classList.contains('whitespace-nowrap')).toBe(true);
            expect(
                Array.from(anchor.classList).filter((className) => className === 'whitespace-nowrap'),
            ).toHaveLength(1);
        }
    });
});
