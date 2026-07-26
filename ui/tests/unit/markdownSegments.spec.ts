import { describe, expect, it } from 'vitest';
import {
    collectMarkdownReferenceDefinitions,
    createMarkdownSegmentDrafts,
} from '@/utils/markdownSegments';

describe('markdownSegments', () => {
    it('seals complete prefix blocks and keeps only streaming tail active', () => {
        const source = '# Heading\n\nFirst paragraph.\n\nSecond paragraph';
        const segments = createMarkdownSegmentDrafts(
            source,
            'response',
            collectMarkdownReferenceDefinitions(source),
            true,
        );

        expect(segments).toHaveLength(3);
        expect(segments.map((segment) => segment.state)).toEqual(['sealed', 'sealed', 'active']);
        expect(segments.map((segment) => segment.source).join('')).toBe(source);
    });

    it('keeps an uncertain open fence suffix together', () => {
        const source = '# Stable\n\nBefore fence.\n\n```ts\nconst value = 1;\n\nStill code';
        const segments = createMarkdownSegmentDrafts(
            source,
            'response',
            collectMarkdownReferenceDefinitions(source),
            true,
        );

        expect(segments.at(-1)?.state).toBe('active');
        expect(segments.at(-1)?.source).toContain('```ts');
        expect(segments.map((segment) => segment.source).join('')).toBe(source);
    });

    it('keeps an uncertain block-math suffix together after streaming ends', () => {
        const source = 'Stable paragraph.\n\n$$\na + b\n\nUncertain tail';
        const segments = createMarkdownSegmentDrafts(
            source,
            'response',
            collectMarkdownReferenceDefinitions(source),
            false,
        );

        expect(segments.at(-1)?.state).toBe('active');
        expect(segments.at(-1)?.source).toContain('$$');
    });

    it('fingerprints only definitions used by each segment', () => {
        const source = '[First][one]\n\nPlain text.\n\n[one]: https://one.example\n[two]: https://two.example';
        const definitions = collectMarkdownReferenceDefinitions(source);
        const segments = createMarkdownSegmentDrafts(source, 'response', definitions, false);

        expect(segments[0]?.parserContextFingerprint).toContain('one:');
        expect(segments[0]?.parserContextFingerprint).not.toContain('two:');
        expect(segments[1]?.parserContextFingerprint).toBe('');
    });
});
