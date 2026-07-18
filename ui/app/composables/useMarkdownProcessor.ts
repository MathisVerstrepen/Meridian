import { createApp } from 'vue';
import type { FetchedPage, WebSearch } from '@/types/webSearch';
import { parseAssistantContent, type ParsedAutoToolSelection } from '@/utils/markdownParsing';
import CodeBlockCopyButton from '~/components/ui/chat/utils/copyButton.vue';

const FullScreenButton = defineAsyncComponent(
    () => import('~/components/ui/chat/utils/fullScreenButton.vue'),
);

type RenderedMarkdownSections = {
    thinkingHtml: string;
    responseHtml: string;
};

type ResponseMarkdownTransformer = (markdown: string) => string;

export const useMarkdownProcessor = (contentRef: Ref<HTMLElement | null>) => {
    const thinkingHtml = ref('');
    const responseHtml = ref('');
    const autoToolSelection = ref<ParsedAutoToolSelection | null>(null);
    const webSearches = ref<WebSearch[]>([]);
    const fetchedPages = ref<FetchedPage[]>([]);
    const isError = ref(false);

    let activeProcessId = 0;

    const resetState = () => {
        thinkingHtml.value = '';
        responseHtml.value = '';
        autoToolSelection.value = null;
        webSearches.value = [];
        fetchedPages.value = [];
        isError.value = false;
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

        autoToolSelection.value = parsed.autoToolSelection;
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
        autoToolSelection,
        webSearches,
        fetchedPages,
        isError,
        processMarkdown,
        enhanceMermaidBlocks,
        enhanceCodeBlocks,
    };
};
