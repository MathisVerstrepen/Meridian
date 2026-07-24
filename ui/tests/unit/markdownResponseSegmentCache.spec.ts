import { describe, expect, it, vi } from 'vitest';
import type { RenderedMarkdownSegment } from '@/composables/useMarkdownProcessor';
import { createResponseSegmentGroupMapper } from '@/utils/markdownResponseSegmentCache';

const createSegment = (renderKey: string, html: string): RenderedMarkdownSegment => ({
    id: renderKey,
    renderKey,
    channel: 'response',
    start: 0,
    end: html.length,
    source: html,
    state: 'sealed',
    html,
    parserContextFingerprint: 'parser',
    enhancementFingerprint: 'enhancement',
    revision: 0,
});

describe('response segment group cache', () => {
    it('reuses derived groups and children for immutable segments', () => {
        const splitHtml = vi.fn((html: string) => [html]);
        const mapGroups = createResponseSegmentGroupMapper(splitHtml);
        const sealedPrefix = createSegment('prefix:0', '<p>Prefix</p>');
        const activeTail = createSegment('tail:0', '<p>Tail</p>');

        const initialGroups = mapGroups([sealedPrefix, activeTail]);
        const changedTail = createSegment('tail:1', '<p>Tail extended</p>');
        const updatedGroups = mapGroups([sealedPrefix, changedTail]);

        expect(splitHtml).toHaveBeenCalledTimes(3);
        expect(updatedGroups[0]).toBe(initialGroups[0]);
        expect(updatedGroups[0]?.children).toBe(initialGroups[0]?.children);
        expect(updatedGroups[1]).not.toBe(initialGroups[1]);
        expect(splitHtml).toHaveBeenLastCalledWith('<p>Tail extended</p>', 'tail:1');
    });
});
