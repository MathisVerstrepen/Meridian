import { createApp, defineAsyncComponent, ref, type Ref } from 'vue';
import type { WebSearch } from '@/types/webSearch';

// --- Type Definitions ---
export type BlockType = 'thinking' | 'response' | 'error';
export type Block = {
    type: BlockType;
    raw: string;
    isComplete: boolean;
};

// --- Component Imports for DOM enhancement ---
const CodeBlockCopyButton = defineAsyncComponent(
    () => import('@/components/ui/chat/utils/copyButton.vue'),
);
const FullScreenButton = defineAsyncComponent(
    () => import('@/components/ui/chat/utils/fullScreenButton.vue'),
);

/**
 * A composable to handle parsing of custom markdown tags and enhancing the rendered HTML.
 * @param contentRef A ref to the HTML element where the response content is rendered.
 */
export const useMarkdownProcessor = (contentRef: Ref<HTMLElement | null>) => {
    // --- State ---
    const thinkingHtml = ref('');
    const responseHtml = ref('');
    const webSearches = ref<WebSearch[]>([]);
    const isError = ref(false);

    // --- Caching State for Thinking Block ---
    const isThinkingBlockComplete = ref(false);
    let completedThinkingRaw: string | null = null;

    // --- Utility Functions ---
    const faviconFromLink = (link: string): string => {
        try {
            const url = new URL(link);
            return `https://www.google.com/s2/favicons?domain=${url.hostname}&sz=32`;
        } catch {
            return ''; // Return empty string for invalid URLs
        }
    };

    const _parseWebSearchResults = (rawText: string): [WebSearch[], string] => {
        const webSearchRegex = /\[WEB_SEARCH\]([\s\S]*?)\[!WEB_SEARCH\]/g;
        const openWebSearchRegex = /\[WEB_SEARCH\]([\s\S]*)$/;

        let remainingText = rawText;

        // Process all complete blocks first
        const completeSearches = Array.from(remainingText.matchAll(webSearchRegex)).flatMap(
            (match) => {
                const content = match[1].trim();
                const searchesInBlock: WebSearch[] = [];
                // Split content by search_query tags. The tag itself is the delimiter.
                const searchChunks = content.split(/<search_query>/s).slice(1); // Discard anything before the first query

                for (const chunk of searchChunks) {
                    // Each chunk now starts with the query content and ends with </search_query>
                    const queryMatch = /^\s*(?:"([^"]+)"|([^<]+?))\s*<\/search_query>/s.exec(chunk);
                    if (!queryMatch) continue;

                    const query = (queryMatch[1] || queryMatch[2]).trim();
                    const results: WebSearch['results'] = [];

                    // The rest of the chunk contains the search results
                    const resultsContent = chunk.substring(queryMatch[0].length);

                    const resRegex =
                        /<search_res>\s*Title:\s*(.+?)\s*URL:\s*(.+?)\s*Content:\s*([\s\S]+?)\s*<\/search_res>/g;
                    let resMatch;
                    while ((resMatch = resRegex.exec(resultsContent)) !== null) {
                        const [, title, link, snippet] = resMatch;
                        results.push({
                            title: title.trim(),
                            link: link.trim(),
                            content: snippet.trim(),
                            favicon: faviconFromLink(link),
                        });
                    }
                    searchesInBlock.push({ query, results, streaming: false });
                }
                return searchesInBlock;
            },
        );

        remainingText = remainingText.replace(webSearchRegex, '');

        // Now, check for a single streaming (open) block
        const streamingMatch = remainingText.match(openWebSearchRegex);
        if (streamingMatch) {
            const content = streamingMatch[1].trim();
            const searchChunks = content.split(/<search_query>/s).slice(1);

            for (let i = 0; i < searchChunks.length; i++) {
                const chunk = searchChunks[i];
                const isLastChunk = i === searchChunks.length - 1;

                const queryMatch = /^\s*(?:"([^"]+)"|([^<]+?))\s*<\/search_query>/s.exec(chunk);
                if (!queryMatch) continue;

                const query = (queryMatch[1] || queryMatch[2]).trim();
                const results: WebSearch['results'] = [];
                const resultsContent = chunk.substring(queryMatch[0].length);
                const resRegex =
                    /<search_res>\s*Title:\s*(.+?)\s*URL:\s*(.+?)\s*Content:\s*([\s\S]+?)\s*<\/search_res>/g;

                let resMatch;
                while ((resMatch = resRegex.exec(resultsContent)) !== null) {
                    const [, title, link, snippet] = resMatch;
                    results.push({
                        title: title.trim(),
                        link: link.trim(),
                        content: snippet.trim(),
                        favicon: faviconFromLink(link),
                    });
                }
                // Only the very last query in a streaming block is considered "streaming"
                completeSearches.push({ query, results, streaming: isLastChunk });
            }
            remainingText = remainingText.replace(openWebSearchRegex, '');
        }

        return [completeSearches, remainingText];
    };

    /**
     * Parses a markdown string for custom tags like [THINK] and [ERROR].
     * @param markdown The raw markdown string.
     * @returns An array of raw content blocks.
     */
    const _parseToRawBlocks = (markdown: string): Block[] => {
        const blocks: Block[] = [];
        let remainingMarkdown = markdown.trim();

        // 1. Check for [ERROR] block (takes precedence)
        const errorRegex = /\[ERROR\]([\s\S]*?)(\[!ERROR\]|$)/;
        const errorMatch = errorRegex.exec(remainingMarkdown);
        if (errorMatch) {
            const isComplete = errorMatch[2] === '[!ERROR]';
            blocks.push({ type: 'error', raw: errorMatch[1].trim(), isComplete });
            return blocks; // If there's an error, we don't process anything else
        }

        // 2. Check for [THINK] block
        const thinkRegex = /\[THINK\]([\s\S]*?)(\[!THINK\]|$)/;
        const thinkMatch = thinkRegex.exec(remainingMarkdown);
        if (thinkMatch) {
            const isComplete = thinkMatch[2] === '[!THINK]';
            blocks.push({ type: 'thinking', raw: thinkMatch[1].trim(), isComplete });
            remainingMarkdown = remainingMarkdown.replace(thinkMatch[0], '').trim();
        }

        // 3. The rest is considered the main response
        if (remainingMarkdown) {
            blocks.push({ type: 'response', raw: remainingMarkdown, isComplete: false });
        }

        return blocks;
    };

    /**
     * Scans for Mermaid blocks and enhances them by wrapping them and adding a fullscreen button.
     * This should be called BEFORE the Mermaid library renders the block to SVG.
     */
    const enhanceMermaidBlocks = () => {
        const container = contentRef.value;
        if (!container) return;

        const mermaidBlocks = Array.from(container.querySelectorAll('pre.mermaid'));
        mermaidBlocks.forEach((block) => {
            if (block.parentElement?.classList.contains('mermaid-wrapper')) return;

            const wrapper = document.createElement('div');
            wrapper.classList.add('mermaid-wrapper', 'relative');

            block.parentElement?.insertBefore(wrapper, block);
            wrapper.appendChild(block);

            const mountNode = document.createElement('div');
            const rawMermaidElement = block.innerHTML;

            const app = createApp(FullScreenButton, {
                renderedElement: block.cloneNode(true),
                rawMermaidElement,
                class: 'hover:bg-stone-gray/20 bg-stone-gray/10 absolute top-2 right-2 h-8 w-8 p-1 backdrop-blur-sm',
            });
            app.mount(mountNode);

            wrapper.appendChild(mountNode);
        });
    };

    /**
     * Scans for code blocks generated by Shiki and enhances them by wrapping them
     * and adding a copy button.
     */
    const enhanceCodeBlocks = () => {
        const container = contentRef.value;
        if (!container) return;

        // The worker wraps Shiki's output (<pre class="...replace-code-containers">) inside another <pre><code>.
        // This selector finds the outer <pre> that contains the one with our special class.
        const codeBlocks = Array.from(container.querySelectorAll('pre')).filter((pre) =>
            pre.querySelector('pre.replace-code-containers'),
        );

        codeBlocks.forEach((pre: Element) => {
            if (pre.parentElement?.classList.contains('code-wrapper')) return;

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

    /**
     * Processes a raw markdown string, parses it into blocks, converts to HTML,
     * and updates the composable's state.
     * @param markdown The raw markdown string.
     * @param markedParser The marked worker's parse function.
     */
    const processMarkdown = async (
        markdown: string,
        markedParser: (md: string) => Promise<string>,
    ) => {
        // Reset state for each new processing job
        isError.value = false;
        if (!markdown) {
            thinkingHtml.value = '';
            responseHtml.value = '';
            webSearches.value = [];
            isThinkingBlockComplete.value = false;
            completedThinkingRaw = null;
            return;
        }

        // 1. Parse out WebSearch objects and get the remaining markdown
        const [parsedSearches, remainingMarkdown] = _parseWebSearchResults(markdown);
        webSearches.value = parsedSearches;

        // 2. Process the rest of the markdown for THINK, ERROR, and RESPONSE blocks
        const rawBlocks = _parseToRawBlocks(remainingMarkdown);

        // If no thinking block is found, ensure its state and HTML are cleared.
        if (!rawBlocks.some((b) => b.type === 'thinking')) {
            thinkingHtml.value = '';
            isThinkingBlockComplete.value = false;
            completedThinkingRaw = null;
        }

        for (const block of rawBlocks) {
            // Error blocks are handled differently: they contain plain text, not markdown.
            if (block.type === 'error') {
                isError.value = true;
                responseHtml.value = block.raw;
                thinkingHtml.value = ''; // Clear other content on error
                return; // Stop processing on error
            }

            try {
                if (block.type === 'thinking') {
                    // ... (existing logic for thinking block remains the same)
                    if (isThinkingBlockComplete.value && completedThinkingRaw === block.raw) {
                        continue;
                    }
                    const html = await markedParser(block.raw);
                    thinkingHtml.value = html;
                    if (block.isComplete) {
                        isThinkingBlockComplete.value = true;
                        completedThinkingRaw = block.raw;
                    } else {
                        isThinkingBlockComplete.value = false;
                        completedThinkingRaw = null;
                    }
                } else if (block.type === 'response') {
                    const html = await markedParser(block.raw);
                    responseHtml.value = html;
                }
            } catch (err) {
                console.error(
                    `Markdown parsing error in [${block.type.toUpperCase()}] block:`,
                    err,
                );
                isError.value = true;
                responseHtml.value = `Error rendering content. Please try again later.`;
            }
        }
    };

    return {
        thinkingHtml,
        responseHtml,
        webSearches,
        isError,
        processMarkdown,
        enhanceMermaidBlocks,
        enhanceCodeBlocks,
    };
};
