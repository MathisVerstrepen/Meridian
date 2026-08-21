import { ToolEnum } from '@/types/enums';
import type { FetchedPage, WebSearch } from '@/types/webSearch';

export type ParsedAutoToolSelection = {
    selectedTools: ToolEnum[];
};

export type ParsedAssistantContent = {
    errorText: string | null;
    autoToolSelection: ParsedAutoToolSelection | null;
    thinkingMarkdown: string;
    responseMarkdown: string;
    webSearches: WebSearch[];
    fetchedPages: FetchedPage[];
};

const INTERNAL_REPLAY_MARKERS = [
    '<executing_code',
    '<sandbox_artifact',
    '[WEB_SEARCH]',
    '<fetch_url',
    '<visualising',
    '<visualising_error',
    '<asking_user',
] as const;
const LEADING_REPLAY_BLOCK_PATTERNS = [
    /^<executing_code(?:\s+[^>]*)?>[\s\S]*?<\/executing_code>\s*/i,
    /^<sandbox_artifact\s+tool_call_id="[^"]+"\s+id="[^"]+"\s+kind="[^"]+"\s+name="[^"]*"\s+path="[^"]*"(?:\s+content_type="[^"]*")?><\/sandbox_artifact>\s*/i,
    /^\[WEB_SEARCH\][\s\S]*?(?:\[!WEB_SEARCH\]|$)\s*/i,
    /^<fetch_url(?:\s+[^>]*)?>([\s\S]*?)<\/fetch_url>(\s*<fetch_error>[\s\S]*?<\/fetch_error>)?\s*/i,
    /^<visualising(?:\s+[^>]*)?>[\s\S]*?<\/visualising>\s*/i,
    /^<visualising_error(?:\s+[^>]*)?>[\s\S]*?<\/visualising_error>\s*/i,
    /^<asking_user(?:\s+[^>]*)?>[\s\S]*?<\/asking_user>\s*/i,
] as const;

const parseAutoToolSelection = (rawText: string): [ParsedAutoToolSelection | null, string] => {
    const autoToolSelectionRegex =
        /<section\s+data-auto-tool-selection="([^"]*)"\s*><\/section>/i;
    const match = autoToolSelectionRegex.exec(rawText);
    if (!match) {
        return [null, rawText];
    }

    const toolValues: ToolEnum[] = Object.values(ToolEnum);
    const selectedTools = match[1]
        .split(',')
        .map((tool) => tool.trim())
        .flatMap((tool) => toolValues.find((value) => value === tool) ?? []);

    return [
        {
            selectedTools,
        },
        rawText.replace(autoToolSelectionRegex, '').trim(),
    ];
};

const faviconFromLink = (link: string): string => {
    try {
        const url = new URL(link);
        return `https://www.google.com/s2/favicons?domain=${url.hostname}&sz=32`;
    } catch {
        return '';
    }
};

const parseFetchedPages = (rawText: string): [FetchedPage[], string] => {
    if (!rawText.includes('<fetch_url')) {
        return [[], rawText];
    }

    const fetchedPageRegex =
        /<fetch_url(?:\s+id="([^"]+)")?(?:\s+duration_ms="[^"]+")?>([\s\S]*?)<\/fetch_url>(\s*<fetch_error>[\s\S]*?<\/fetch_error>)?/g;
    const pages: FetchedPage[] = [];

    const remainingText = rawText.replace(
        fetchedPageRegex,
        (match, toolCallId, urlBlock, errorBlock) => {
            const urlMatch = /Reading content from:\s*(\S+)/.exec(urlBlock.trim());
            if (!urlMatch) {
                return match;
            }

            const url = urlMatch[1].trim();

            if (errorBlock) {
                const errorMatch = /<fetch_error>([\s\S]*?)<\/fetch_error>/.exec(errorBlock);
                if (!errorMatch) {
                    return '';
                }

                const rawContent = errorMatch[1].trim();
                const successPrefix = `Content from ${url}:`;
                const cleanContent = rawContent.startsWith(successPrefix)
                    ? rawContent.substring(successPrefix.length).trim()
                    : rawContent;

                pages.push({
                    url,
                    toolCallId: toolCallId || undefined,
                    error: cleanContent,
                });
                return '';
            }

            pages.push({
                url,
                toolCallId: toolCallId || undefined,
            });
            return '';
        },
    );

    return [pages, remainingText];
};

const parseWebSearches = (rawText: string): [WebSearch[], string] => {
    if (!rawText.includes('[WEB_SEARCH]') && !rawText.includes('<search_query')) {
        return [[], rawText];
    }

    const webSearchRegex = /\[WEB_SEARCH\]([\s\S]*?)\[!WEB_SEARCH\]/g;
    const openWebSearchRegex = /\[WEB_SEARCH\]([\s\S]*)$/;
    const searchEntryRegex =
        /<search_query(?:\s+id="([^"]+)")?(?:\s+duration_ms="[^"]+")?>([\s\S]*?)<\/search_query>\s*((?:<search_res>\s*Title:\s*.+?\s*URL:\s*.+?\s*Content:\s*[\s\S]+?\s*<\/search_res>\s*)+|<search_error>[\s\S]*?<\/search_error>\s*)?/g;

    const parsedSearches: WebSearch[] = [];
    let remainingText = rawText;

    const parseSearchEntry = (
        toolCallId: string | undefined,
        queryBlock: string,
        resultsContent: string,
        isStreaming = false,
    ): WebSearch | null => {
        const queryMatch = /^\s*(?:"([^"]+)"|([^<]+?))\s*$/s.exec(queryBlock.trim());
        if (!queryMatch) {
            return null;
        }

        const query = (queryMatch[1] || queryMatch[2]).trim();
        const results: WebSearch['results'] = [];
        let error: string | undefined;

        const errorMatch = /<search_error>([\s\S]*?)<\/search_error>/.exec(resultsContent);
        if (errorMatch) {
            error = errorMatch[1].trim();
        } else {
            const resultRegex =
                /<search_res>\s*Title:\s*(.+?)\s*URL:\s*(.+?)\s*Content:\s*([\s\S]+?)\s*<\/search_res>/g;
            let resultMatch;
            while ((resultMatch = resultRegex.exec(resultsContent)) !== null) {
                const [, title, link, snippet] = resultMatch;
                results.push({
                    title: title.trim(),
                    link: link.trim(),
                    content: snippet.trim(),
                    favicon: faviconFromLink(link),
                });
            }
        }

        return {
            query,
            toolCallId: toolCallId || undefined,
            results,
            streaming: isStreaming,
            error,
        };
    };

    const parseSearchBlock = (content: string, isStreamingBlock: boolean): WebSearch[] => {
        const entries = Array.from(content.matchAll(searchEntryRegex));

        return entries
            .map((entry, index) =>
                parseSearchEntry(
                    entry[1] || undefined,
                    entry[2] || '',
                    entry[3] || '',
                    isStreamingBlock && index === entries.length - 1,
                ),
            )
            .filter((entry): entry is WebSearch => entry !== null);
    };

    remainingText = remainingText.replace(webSearchRegex, (_match, content) => {
        parsedSearches.push(...parseSearchBlock(content.trim(), false));
        return '';
    });

    const streamingMatch = remainingText.match(openWebSearchRegex);
    if (streamingMatch) {
        parsedSearches.push(...parseSearchBlock(streamingMatch[1].trim(), true));
        remainingText = remainingText.replace(openWebSearchRegex, '');
    }

    remainingText = remainingText.replace(
        searchEntryRegex,
        (match, toolCallId, queryBlock, resultsContent) => {
            const parsedEntry = parseSearchEntry(
                toolCallId || undefined,
                queryBlock || '',
                resultsContent || '',
            );
            if (!parsedEntry) {
                return match;
            }

            parsedSearches.push(parsedEntry);
            return '';
        },
    );

    remainingText = remainingText.replace(/\[WEB_SEARCH\]|\[!WEB_SEARCH\]/g, '');

    return [parsedSearches, remainingText];
};

const trimAtInternalReplayMarker = (text: string): string => {
    const replayMarkers = ['\n[THINK]'];

    let replayIndex = -1;
    for (const marker of replayMarkers) {
        const markerIndex = text.indexOf(marker);
        if (markerIndex !== -1 && (replayIndex === -1 || markerIndex < replayIndex)) {
            replayIndex = markerIndex;
        }
    }

    return replayIndex === -1 ? text.trim() : text.slice(0, replayIndex).trimEnd();
};

const stripLeadingReplayBlocks = (text: string): string => {
    let remainingText = text.trimStart();
    let foundReplayBlock = false;
    let changed = true;

    while (changed) {
        changed = false;

        for (const pattern of LEADING_REPLAY_BLOCK_PATTERNS) {
            if (!pattern.test(remainingText)) {
                continue;
            }

            remainingText = remainingText.replace(pattern, '').trimStart();
            foundReplayBlock = true;
            changed = true;
            break;
        }
    }

    return foundReplayBlock ? remainingText : text;
};

const splitThinkingAndResponse = (
    rawText: string,
) => {
    const trimmed = rawText.trim();
    const thinkOpenTag = '[THINK]';
    const thinkCloseTag = '[!THINK]';
    const thinkingSegments: string[] = [];
    const responseSegments: string[] = [];
    const appendResponseSegment = (segment: string, options?: { trimReplayTail?: boolean }) => {
        const nextSegment = options?.trimReplayTail ? trimAtInternalReplayMarker(segment) : segment;
        if (nextSegment) {
            responseSegments.push(nextSegment);
        }
    };
    let cursor = 0;

    while (cursor < trimmed.length) {
        const openIndex = trimmed.indexOf(thinkOpenTag, cursor);
        if (openIndex === -1) {
            appendResponseSegment(trimmed.slice(cursor), { trimReplayTail: true });
            break;
        }

        appendResponseSegment(trimmed.slice(cursor, openIndex));

        const thinkingStart = openIndex + thinkOpenTag.length;
        const closeIndex = trimmed.indexOf(thinkCloseTag, thinkingStart);
        if (closeIndex !== -1) {
            const thinkingBlock = trimmed.slice(thinkingStart, closeIndex).trim();
            if (thinkingBlock) {
                thinkingSegments.push(thinkingBlock);
            }
            cursor = closeIndex + thinkCloseTag.length;
            continue;
        }

        const thinkingTail = trimmed.slice(thinkingStart);
        let responseStartIndex = -1;

        for (const marker of INTERNAL_REPLAY_MARKERS) {
            const markerIndex = thinkingTail.indexOf(marker);
            if (
                markerIndex !== -1 &&
                (responseStartIndex === -1 || markerIndex < responseStartIndex)
            ) {
                responseStartIndex = markerIndex;
            }
        }

        if (responseStartIndex !== -1) {
            const thinkingBlock = thinkingTail.slice(0, responseStartIndex).trim();
            if (thinkingBlock) {
                thinkingSegments.push(thinkingBlock);
            }
            appendResponseSegment(stripLeadingReplayBlocks(thinkingTail.slice(responseStartIndex)), {
                trimReplayTail: true,
            });
        } else {
            const thinkingBlock = thinkingTail.trim();
            if (thinkingBlock) {
                thinkingSegments.push(thinkingBlock);
            }
        }
        break;
    }

    return {
        thinkingMarkdown: thinkingSegments.join('\n\n').trim(),
        responseMarkdown: responseSegments.join('').trim(),
    };
};

export const parseAssistantContent = (markdown: string): ParsedAssistantContent => {
    const rawText = markdown.trim();
    if (!rawText) {
        return {
            errorText: null,
            autoToolSelection: null,
            thinkingMarkdown: '',
            responseMarkdown: '',
            webSearches: [],
            fetchedPages: [],
        };
    }

    const errorMatch = /\[ERROR\]([\s\S]*?)(?:\[!ERROR\]|$)/.exec(rawText);
    if (errorMatch) {
        return {
            errorText: errorMatch[1].trim(),
            autoToolSelection: null,
            thinkingMarkdown: '',
            responseMarkdown: '',
            webSearches: [],
            fetchedPages: [],
        };
    }

    const [parsedAutoToolSelection, afterAutoToolSelection] = parseAutoToolSelection(rawText);
    const [parsedPages, afterPages] = parseFetchedPages(afterAutoToolSelection);
    const [parsedSearches, afterSearches] = parseWebSearches(afterPages);
    const { thinkingMarkdown, responseMarkdown } = splitThinkingAndResponse(afterSearches);

    return {
        errorText: null,
        autoToolSelection: parsedAutoToolSelection,
        thinkingMarkdown,
        responseMarkdown,
        webSearches: parsedSearches,
        fetchedPages: parsedPages,
    };
};
