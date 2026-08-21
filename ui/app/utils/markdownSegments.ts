import { Marked } from 'marked';

export type MarkdownSegmentChannel = 'thinking' | 'response';
export type MarkdownSegmentState = 'sealed' | 'active';

export type MarkdownSegmentDraft = {
    channel: MarkdownSegmentChannel;
    start: number;
    end: number;
    source: string;
    state: MarkdownSegmentState;
    parserContextFingerprint: string;
    enhancementFingerprint: string;
};

export type MarkdownReferenceDefinitions = Map<string, string>;

const segmentLexer = new Marked({
    gfm: true,
    breaks: false,
    pedantic: false,
});

const REFERENCE_DEFINITION_REGEX =
    /^[ \t]{0,3}\[([^\]]+)\]:[ \t]*(\S+)(?:[ \t]+(?:"[^"]*"|'[^']*'|\([^)]*\)))?[ \t]*(?:\n|$)/gm;
const REFERENCE_USAGE_REGEX = /!?\[([^\]]+)\](?:[ \t]*\[([^\]]*)\])?/g;
const FENCE_LINE_REGEX = /^( {0,3})(`{3,}|~{3,})[^\n]*(?:\n|$)/gm;

const normalizeReferenceLabel = (label: string): string =>
    label.trim().replace(/\s+/g, ' ').toLowerCase();

export const collectMarkdownReferenceDefinitions = (
    ...sources: string[]
): MarkdownReferenceDefinitions => {
    const definitions: MarkdownReferenceDefinitions = new Map();

    for (const source of sources) {
        REFERENCE_DEFINITION_REGEX.lastIndex = 0;
        for (const match of source.matchAll(REFERENCE_DEFINITION_REGEX)) {
            const label = normalizeReferenceLabel(match[1] || '');
            if (label && !definitions.has(label)) {
                definitions.set(label, match[0].trimEnd());
            }
        }
    }

    return definitions;
};

const collectUsedReferenceLabels = (
    source: string,
    definitions: MarkdownReferenceDefinitions,
): string[] => {
    const labels = new Set<string>();
    REFERENCE_USAGE_REGEX.lastIndex = 0;

    for (const match of source.matchAll(REFERENCE_USAGE_REGEX)) {
        const matchEnd = (match.index ?? 0) + match[0].length;
        if (source[matchEnd] === '(') {
            continue;
        }

        const explicitLabel = match[2];
        const label = normalizeReferenceLabel(explicitLabel || match[1] || '');
        if (definitions.has(label)) {
            labels.add(label);
        }
    }

    return [...labels].sort();
};

const buildParserContextFingerprint = (
    source: string,
    definitions: MarkdownReferenceDefinitions,
): string => {
    const usedLabels = collectUsedReferenceLabels(source, definitions);
    return usedLabels.map((label) => `${label}:${definitions.get(label)}`).join('\n');
};

const findUnclosedFenceStart = (source: string): number | null => {
    let openFence: { marker: string; length: number; start: number } | null = null;
    FENCE_LINE_REGEX.lastIndex = 0;

    for (const match of source.matchAll(FENCE_LINE_REGEX)) {
        const fence = match[2] || '';
        const marker = fence[0] || '';
        if (!openFence) {
            openFence = { marker, length: fence.length, start: match.index ?? 0 };
        } else if (marker === openFence.marker && fence.length >= openFence.length) {
            openFence = null;
        }
    }

    return openFence?.start ?? null;
};

const findUnclosedBlockMathStart = (source: string): number | null => {
    let openStart: number | null = null;
    for (let index = 0; index < source.length - 1; index += 1) {
        if (source[index] !== '$' || source[index + 1] !== '$' || source[index - 1] === '\\') {
            continue;
        }
        openStart = openStart === null ? index : null;
        index += 1;
    }
    return openStart;
};

type RawBlock = {
    start: number;
    end: number;
    source: string;
    type: string;
};

const lexRawBlocks = (source: string): RawBlock[] => {
    if (!source) {
        return [];
    }

    try {
        const tokens = segmentLexer.lexer(source);
        const blocks: RawBlock[] = [];
        let cursor = 0;

        for (const token of tokens) {
            const raw = token.raw;
            if (!isRuntimeString(raw) || !raw) {
                return [{ start: 0, end: source.length, source, type: 'uncertain' }];
            }

            const start = cursor;
            cursor += raw.length;
            if (token.type === 'space' && blocks.length) {
                const previous = blocks[blocks.length - 1]!;
                previous.end = cursor;
                previous.source += raw;
                continue;
            }

            blocks.push({ start, end: cursor, source: raw, type: token.type });
        }

        if (cursor !== source.length || !blocks.length) {
            return [{ start: 0, end: source.length, source, type: 'uncertain' }];
        }
        return blocks;
    } catch {
        return [{ start: 0, end: source.length, source, type: 'uncertain' }];
    }
};

const findUncertainSuffixStart = (source: string, blocks: RawBlock[]): number | null => {
    const candidates: number[] = [];
    const fenceStart = findUnclosedFenceStart(source);
    const mathStart = findUnclosedBlockMathStart(source);
    if (fenceStart !== null) candidates.push(fenceStart);
    if (mathStart !== null) candidates.push(mathStart);

    const uncertainBlock = blocks.find((block) => {
        if (block.type === 'uncertain') return true;
        if (block.type !== 'html') return false;
        return !/^<div\b[^>]*>[\s\S]*<\/div>\s*$/i.test(block.source.trim());
    });
    if (uncertainBlock) candidates.push(uncertainBlock.start);

    return candidates.length ? Math.min(...candidates) : null;
};

const mergeUncertainSuffix = (blocks: RawBlock[], uncertainStart: number | null): RawBlock[] => {
    if (uncertainStart === null) {
        return blocks;
    }

    const firstAffectedIndex = blocks.findIndex((block) => block.end > uncertainStart);
    if (firstAffectedIndex < 0) {
        return blocks;
    }

    const prefix = blocks.slice(0, firstAffectedIndex);
    const suffix = blocks.slice(firstAffectedIndex);
    const first = suffix[0]!;
    const last = suffix[suffix.length - 1]!;
    return [
        ...prefix,
        {
            start: first.start,
            end: last.end,
            source: suffix.map((block) => block.source).join(''),
            type: 'uncertain',
        },
    ];
};

export const createMarkdownSegmentDrafts = (
    source: string,
    channel: MarkdownSegmentChannel,
    definitions: MarkdownReferenceDefinitions,
    isStreaming: boolean,
): MarkdownSegmentDraft[] => {
    const rawBlocks = lexRawBlocks(source);
    const uncertainStart = findUncertainSuffixStart(source, rawBlocks);
    const blocks = mergeUncertainSuffix(rawBlocks, uncertainStart);

    return blocks.map((block, index) => ({
        channel,
        start: block.start,
        end: block.end,
        source: block.source,
        state:
            index === blocks.length - 1 && (isStreaming || uncertainStart !== null)
                ? 'active'
                : 'sealed',
        parserContextFingerprint: buildParserContextFingerprint(block.source, definitions),
        enhancementFingerprint: block.source,
    }));
};

export const buildMarkdownSegmentParserInput = (
    segmentSource: string,
    parserContextFingerprint: string,
): string => {
    if (!parserContextFingerprint) {
        return segmentSource;
    }

    const definitions = parserContextFingerprint
        .split('\n')
        .map((entry) => entry.slice(entry.indexOf(':') + 1))
        .join('\n');
    return `${segmentSource}\n\n${definitions}`;
};
import { isRuntimeString } from '@/utils/runtimeTypes';
