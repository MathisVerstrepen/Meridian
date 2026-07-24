import type { FetchedPage, WebSearch } from '@/types/webSearch';
import { parseAssistantContent, type ParsedAutoToolSelection } from '@/utils/markdownParsing';
import {
    buildMarkdownSegmentParserInput,
    collectMarkdownReferenceDefinitions,
    createMarkdownSegmentDrafts,
    type MarkdownSegmentChannel,
    type MarkdownSegmentDraft,
    type MarkdownSegmentState,
} from '@/utils/markdownSegments';

type ResponseMarkdownTransformer = (markdown: string) => string;

export type RenderedMarkdownSegment = Readonly<{
    id: string;
    renderKey: string;
    channel: MarkdownSegmentChannel;
    start: number;
    end: number;
    source: string;
    state: MarkdownSegmentState;
    html: string;
    parserContextFingerprint: string;
    enhancementFingerprint: string;
    revision: number;
}>;

export type MarkdownProcessOptions = {
    cacheKey?: string;
    isStreaming?: boolean;
};

export type MarkdownProcessResult = {
    committed: boolean;
    changedResponseRenderKeys: string[];
    obsoleteResponseRenderKeys: string[];
    parsedSegmentCount: number;
    reusedSegmentCount: number;
};

type ChannelBuild = {
    segments: RenderedMarkdownSegment[];
    parseJobs: Array<Promise<void>>;
    parsedSegmentCount: number;
    reusedSegmentCount: number;
};

const emptyResult = (committed: boolean): MarkdownProcessResult => ({
    committed,
    changedResponseRenderKeys: [],
    obsoleteResponseRenderKeys: [],
    parsedSegmentCount: 0,
    reusedSegmentCount: 0,
});

export const useMarkdownProcessor = () => {
    const thinkingSegments = shallowRef<RenderedMarkdownSegment[]>([]);
    const responseSegments = shallowRef<RenderedMarkdownSegment[]>([]);
    const thinkingHtml = computed(() => thinkingSegments.value.map((segment) => segment.html).join(''));
    const responseHtml = computed(() => responseSegments.value.map((segment) => segment.html).join(''));
    const autoToolSelection = ref<ParsedAutoToolSelection | null>(null);
    const webSearches = ref<WebSearch[]>([]);
    const fetchedPages = ref<FetchedPage[]>([]);
    const isError = ref(false);

    let activeProcessId = 0;
    let committedCacheKey: string | null = null;
    let nextSegmentId = 0;

    const createSegmentId = (channel: MarkdownSegmentChannel): string => {
        nextSegmentId += 1;
        return `${channel}-${nextSegmentId}`;
    };

    const buildChannel = (
        drafts: MarkdownSegmentDraft[],
        previous: RenderedMarkdownSegment[],
        parser: (markdown: string) => Promise<string>,
        canReuseCache: boolean,
    ): ChannelBuild => {
        const segments: RenderedMarkdownSegment[] = [];
        const parseJobs: Array<Promise<void>> = [];
        let parsedSegmentCount = 0;
        let reusedSegmentCount = 0;

        for (const [index, draft] of drafts.entries()) {
            const prior = canReuseCache ? previous[index] : undefined;
            const reusable = Boolean(
                prior &&
                    prior.channel === draft.channel &&
                    prior.start === draft.start &&
                    prior.end === draft.end &&
                    prior.source === draft.source &&
                    prior.parserContextFingerprint === draft.parserContextFingerprint &&
                    prior.enhancementFingerprint === draft.enhancementFingerprint,
            );

            if (reusable && prior) {
                reusedSegmentCount += 1;
                segments.push(
                    prior.state === draft.state
                        ? prior
                        : Object.freeze({ ...prior, state: draft.state }),
                );
                continue;
            }

            const id = prior?.id ?? createSegmentId(draft.channel);
            const revision = prior ? prior.revision + 1 : 0;
            const candidate: { value?: RenderedMarkdownSegment } = {};
            parsedSegmentCount += 1;
            parseJobs.push(
                parser(
                    buildMarkdownSegmentParserInput(
                        draft.source,
                        draft.parserContextFingerprint,
                    ),
                ).then((html) => {
                    candidate.value = Object.freeze({
                        ...draft,
                        id,
                        renderKey: `${id}:${revision}`,
                        revision,
                        html,
                    });
                }),
            );
            Object.defineProperty(segments, index, {
                configurable: true,
                enumerable: true,
                get: () => candidate.value!,
            });
        }

        return { segments, parseJobs, parsedSegmentCount, reusedSegmentCount };
    };

    const commitSegments = (
        cacheKey: string,
        nextThinking: RenderedMarkdownSegment[],
        nextResponse: RenderedMarkdownSegment[],
        metadata: {
            autoToolSelection: ParsedAutoToolSelection | null;
            webSearches: WebSearch[];
            fetchedPages: FetchedPage[];
            isError: boolean;
        },
        counts: { parsedSegmentCount: number; reusedSegmentCount: number },
    ): MarkdownProcessResult => {
        const previousKeys = new Set(responseSegments.value.map((segment) => segment.renderKey));
        const nextKeys = new Set(nextResponse.map((segment) => segment.renderKey));
        const changedResponseRenderKeys = nextResponse
            .filter((segment) => !previousKeys.has(segment.renderKey))
            .map((segment) => segment.renderKey);
        const obsoleteResponseRenderKeys = responseSegments.value
            .filter((segment) => !nextKeys.has(segment.renderKey))
            .map((segment) => segment.renderKey);

        thinkingSegments.value = nextThinking;
        responseSegments.value = nextResponse;
        autoToolSelection.value = metadata.autoToolSelection;
        webSearches.value = metadata.webSearches;
        fetchedPages.value = metadata.fetchedPages;
        isError.value = metadata.isError;
        committedCacheKey = cacheKey;

        return {
            committed: true,
            changedResponseRenderKeys,
            obsoleteResponseRenderKeys,
            ...counts,
        };
    };

    const processMarkdown = async (
        markdown: string,
        markedParser: (md: string) => Promise<string>,
        responseMarkdownTransformer?: ResponseMarkdownTransformer,
        options: MarkdownProcessOptions = {},
    ): Promise<MarkdownProcessResult> => {
        const processId = ++activeProcessId;
        const cacheKey = options.cacheKey ?? 'default';
        const canReuseCache = committedCacheKey === cacheKey;

        if (!markdown) {
            return commitSegments(
                cacheKey,
                [],
                [],
                { autoToolSelection: null, webSearches: [], fetchedPages: [], isError: false },
                { parsedSegmentCount: 0, reusedSegmentCount: 0 },
            );
        }

        const parsed = parseAssistantContent(markdown);
        const metadata = {
            autoToolSelection: parsed.autoToolSelection,
            webSearches: parsed.webSearches,
            fetchedPages: parsed.fetchedPages,
            isError: parsed.errorText !== null,
        };

        if (parsed.errorText !== null) {
            const segment = Object.freeze({
                id: createSegmentId('response'),
                renderKey: `response-error:${processId}`,
                channel: 'response' as const,
                start: 0,
                end: parsed.errorText.length,
                source: parsed.errorText,
                state: 'sealed' as const,
                html: parsed.errorText,
                parserContextFingerprint: '',
                enhancementFingerprint: parsed.errorText,
                revision: 0,
            });
            return commitSegments(cacheKey, [], [segment], metadata, {
                parsedSegmentCount: 0,
                reusedSegmentCount: 0,
            });
        }

        const responseMarkdown = (
            responseMarkdownTransformer
                ? responseMarkdownTransformer(parsed.responseMarkdown)
                : parsed.responseMarkdown
        ).trim();
        const definitions = collectMarkdownReferenceDefinitions(
            parsed.thinkingMarkdown,
            responseMarkdown,
        );
        const thinkingDrafts = createMarkdownSegmentDrafts(
            parsed.thinkingMarkdown,
            'thinking',
            definitions,
            options.isStreaming ?? false,
        );
        const responseDrafts = createMarkdownSegmentDrafts(
            responseMarkdown,
            'response',
            definitions,
            options.isStreaming ?? false,
        );
        const thinkingBuild = buildChannel(
            thinkingDrafts,
            thinkingSegments.value,
            markedParser,
            canReuseCache,
        );
        const responseBuild = buildChannel(
            responseDrafts,
            responseSegments.value,
            markedParser,
            canReuseCache,
        );

        try {
            await Promise.all([...thinkingBuild.parseJobs, ...responseBuild.parseJobs]);
            if (processId !== activeProcessId) {
                return emptyResult(false);
            }

            return commitSegments(
                cacheKey,
                [...thinkingBuild.segments],
                [...responseBuild.segments],
                metadata,
                {
                    parsedSegmentCount:
                        thinkingBuild.parsedSegmentCount + responseBuild.parsedSegmentCount,
                    reusedSegmentCount:
                        thinkingBuild.reusedSegmentCount + responseBuild.reusedSegmentCount,
                },
            );
        } catch (err) {
            console.error('[useMarkdownProcessor] Parsing failed:', err);
            if (processId !== activeProcessId) {
                return emptyResult(false);
            }

            const fallback = responseMarkdown
                ? [
                      Object.freeze({
                          id: createSegmentId('response'),
                          renderKey: `response-fallback:${processId}`,
                          channel: 'response' as const,
                          start: 0,
                          end: responseMarkdown.length,
                          source: responseMarkdown,
                          state: 'active' as const,
                          html: responseMarkdown,
                          parserContextFingerprint: '',
                          enhancementFingerprint: responseMarkdown,
                          revision: 0,
                      }),
                  ]
                : [];
            const result = commitSegments(cacheKey, [], fallback, metadata, {
                parsedSegmentCount:
                    thinkingBuild.parsedSegmentCount + responseBuild.parsedSegmentCount,
                reusedSegmentCount: 0,
            });
            committedCacheKey = null;
            return result;
        }
    };

    return {
        thinkingSegments,
        responseSegments,
        thinkingHtml,
        responseHtml,
        autoToolSelection,
        webSearches,
        fetchedPages,
        isError,
        processMarkdown,
    };
};
