import { createApp } from 'vue';
import type { FetchedPage, WebSearch } from '@/types/webSearch';
import CodeBlockCopyButton from '~/components/ui/chat/utils/copyButton.vue';

const FullScreenButton = defineAsyncComponent(
    () => import('~/components/ui/chat/utils/fullScreenButton.vue'),
);

type ParsedAssistantContent = {
    errorText: string | null;
    thinkingMarkdown: string;
    responseMarkdown: string;
    webSearches: WebSearch[];
    fetchedPages: FetchedPage[];
};

type RenderedMarkdownSections = {
    thinkingHtml: string;
    responseHtml: string;
};

type ResponseMarkdownTransformer = (markdown: string) => string;

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

export const useMarkdownProcessor = (contentRef: Ref<HTMLElement | null>) => {
    const thinkingHtml = ref('');
    const responseHtml = ref('');
    const webSearches = ref<WebSearch[]>([]);
    const fetchedPages = ref<FetchedPage[]>([]);
    const isError = ref(false);

    let activeProcessId = 0;

    const resetState = () => {
        thinkingHtml.value = '';
        responseHtml.value = '';
        webSearches.value = [];
        fetchedPages.value = [];
        isError.value = false;
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
    ): { thinkingMarkdown: string; responseMarkdown: string } => {
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

    const parseAssistantContent = (markdown: string): ParsedAssistantContent => {
        const rawText = markdown.trim();
        if (!rawText) {
            return {
                errorText: null,
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
                thinkingMarkdown: '',
                responseMarkdown: '',
                webSearches: [],
                fetchedPages: [],
            };
        }

        const [parsedPages, afterPages] = parseFetchedPages(rawText);
        const [parsedSearches, afterSearches] = parseWebSearches(afterPages);
        const { thinkingMarkdown, responseMarkdown } = splitThinkingAndResponse(afterSearches);

        return {
            errorText: null,
            thinkingMarkdown,
            responseMarkdown,
            webSearches: parsedSearches,
            fetchedPages: parsedPages,
        };
    };

    const parseMarkdownSections = async (
        thinkingMarkdown: string,
        responseMarkdown: string,
        markedParser: (md: string) => Promise<string>,
    ): Promise<RenderedMarkdownSections> => {
        if (thinkingMarkdown && responseMarkdown) {
            const separator = `<div data-markdown-renderer-split="${crypto.randomUUID()}"></div>`;
            const combinedHtml = await markedParser(
                `${thinkingMarkdown}\n\n${separator}\n\n${responseMarkdown}`,
            );
            const splitSections = combinedHtml.split(separator);

            if (splitSections.length === 2) {
                return {
                    thinkingHtml: splitSections[0],
                    responseHtml: splitSections[1],
                };
            }
        }

        const [thinkingHtml, responseHtml] = await Promise.all([
            thinkingMarkdown ? markedParser(thinkingMarkdown) : Promise.resolve(''),
            responseMarkdown ? markedParser(responseMarkdown) : Promise.resolve(''),
        ]);

        return {
            thinkingHtml,
            responseHtml,
        };
    };

    const enhanceMermaidBlocks = (rawMermaidElements: string[]) => {
        const container = contentRef.value;
        if (!container) {
            return;
        }

        const mermaidBlocks = Array.from(container.querySelectorAll('pre.mermaid'));
        mermaidBlocks.forEach((block, index) => {
            if (block.parentElement?.classList.contains('mermaid-wrapper')) {
                return;
            }

            const wrapper = document.createElement('div');
            wrapper.classList.add('mermaid-wrapper', 'relative');

            block.parentElement?.insertBefore(wrapper, block);
            wrapper.appendChild(block);

            const mountNode = document.createElement('div');
            const rawMermaidElement = rawMermaidElements[index] || '';

            const app = createApp(FullScreenButton, {
                renderedElement: block.cloneNode(true),
                rawMermaidElement,
                class: 'hover:bg-stone-gray/20 bg-stone-gray/10 absolute top-2 right-2 h-8 w-8 p-1 backdrop-blur-sm',
            });
            app.mount(mountNode);

            wrapper.appendChild(mountNode);
        });
    };

    const enhanceCodeBlocks = () => {
        const container = contentRef.value;
        if (!container) {
            return;
        }

        const codeBlocks = Array.from(container.querySelectorAll('pre')).filter((pre) =>
            pre.querySelector('pre.replace-code-containers'),
        );

        codeBlocks.forEach((pre: Element) => {
            if (pre.parentElement?.classList.contains('code-wrapper')) {
                return;
            }

            const wrapper = document.createElement('div');
            wrapper.classList.add('code-wrapper', 'relative');

            pre.parentElement?.insertBefore(wrapper, pre);
            wrapper.appendChild(pre);

            pre.classList.add('overflow-x-auto', 'rounded-lg', 'custom_scroll', 'bg-[#121212]');
            const mountNode = document.createElement('div');

            const app = createApp(CodeBlockCopyButton, {
                textToCopy: (pre as HTMLElement).innerText || '',
                class: 'hover:bg-stone-gray/20 bg-stone-gray/10 absolute top-2 right-2 h-8 w-8 p-1 backdrop-blur-sm',
            });
            app.mount(mountNode);

            wrapper.appendChild(mountNode);
        });
    };

    const processMarkdown = async (
        markdown: string,
        markedParser: (md: string) => Promise<string>,
        responseMarkdownTransformer?: ResponseMarkdownTransformer,
    ) => {
        const processId = ++activeProcessId;

        if (!markdown) {
            resetState();
            return;
        }

        const parsed = parseAssistantContent(markdown);

        webSearches.value = parsed.webSearches;
        fetchedPages.value = parsed.fetchedPages;
        isError.value = parsed.errorText !== null;

        if (parsed.errorText !== null) {
            thinkingHtml.value = '';
            responseHtml.value = parsed.errorText;
            return;
        }

        const responseMarkdown = (
            responseMarkdownTransformer
                ? responseMarkdownTransformer(parsed.responseMarkdown)
                : parsed.responseMarkdown
        ).trim();
        try {
            const { thinkingHtml: thinking, responseHtml: response } = await parseMarkdownSections(
                parsed.thinkingMarkdown,
                responseMarkdown,
                markedParser,
            );

            if (processId !== activeProcessId) {
                return;
            }

            thinkingHtml.value = thinking;
            responseHtml.value = response;
        } catch (err) {
            console.error('[useMarkdownProcessor] Parsing failed:', err);
            if (processId !== activeProcessId) {
                return;
            }
            thinkingHtml.value = '';
            responseHtml.value = responseMarkdown;
        }
    };

    return {
        thinkingHtml,
        responseHtml,
        webSearches,
        fetchedPages,
        isError,
        processMarkdown,
        enhanceMermaidBlocks,
        enhanceCodeBlocks,
    };
};
