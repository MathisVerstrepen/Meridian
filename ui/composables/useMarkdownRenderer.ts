import type { FileTreeNode } from '@/types/github';

/**
 * A composable for parsing and rendering markdown content from chat messages.
 * It handles special tags like [THINK], [ERROR], and extracts file content.
 */
export function useMarkdownRenderer() {
    // --- Composables ---
    const { $markedWorker } = useNuxtApp();
    const { error: showError } = useToast();
    const { renderMermaidCharts } = useMermaid();

    // --- State ---
    const thinkingHtml = ref<string>('');
    const responseHtml = ref<string>('');
    const error = ref<boolean>(false);
    const extractedGithubFiles = ref<FileTreeNode[]>([]);

    // --- Private Helpers ---
    const separateThinkFromResponse = (markdown: string): { thinking: string; response: string } => {
        const fullThinkTagRegex = /\[THINK\]([\s\S]*?)\[!THINK\]/;
        const openThinkTagRegex = /\[THINK\]([\s\S]*)$/;

        const fullTagMatch = fullThinkTagRegex.exec(markdown);
        if (fullTagMatch) {
            return {
                thinking: fullTagMatch[1],
                response: markdown.replace(fullThinkTagRegex, ''),
            };
        }

        const openTagMatch = openThinkTagRegex.exec(markdown);
        if (openTagMatch) {
            return {
                thinking: openTagMatch[1],
                response: '',
            };
        }

        return { thinking: '', response: markdown };
    };

    const parseErrorTag = (markdown: string): string => {
        const startTag = '[ERROR]';
        const endTag = '[!ERROR]';
        const trimmed = markdown.trim();

        if (trimmed.startsWith(startTag)) {
            const endIndex = trimmed.indexOf(endTag);
            const content =
                endIndex !== -1
                    ? trimmed.slice(startTag.length, endIndex)
                    : trimmed.slice(startTag.length);
            error.value = true;
            return content.trim();
        }

        if (trimmed.endsWith(endTag)) {
            const startIndex = trimmed.indexOf(startTag);
            const content =
                startIndex !== -1
                    ? trimmed.slice(startIndex + startTag.length, trimmed.length - endTag.length)
                    : trimmed.slice(0, trimmed.length - endTag.length);
            error.value = true;
            return content.trim();
        }

        return '';
    };

    // --- Public API ---

    /**
     * Processes an assistant's message markdown, updating reactive state with parsed HTML.
     * @param markdown The raw markdown string from the assistant message.
     * @returns A promise resolving to an object indicating if Mermaid diagrams were found.
     */
    const processAssistantMessage = async (markdown: string): Promise<{ hasMermaid: boolean }> => {
        error.value = false;
        let hasMermaid = false;

        if (!markdown) {
            responseHtml.value = '';
            thinkingHtml.value = '';
            return { hasMermaid: false };
        }

        const errorMessage = parseErrorTag(markdown);
        if (errorMessage) {
            responseHtml.value = errorMessage;
            error.value = true;
            return { hasMermaid: false };
        }

        const { thinking, response } = separateThinkFromResponse(markdown);

        // Parse thinking part
        if (thinking) {
            try {
                thinkingHtml.value = await $markedWorker.parse(thinking);
            } catch (err) {
                console.error('Markdown parsing error in [THINK] block:', err);
                thinkingHtml.value = `<p class="text-red-500">Error rendering thinking block.</p>`;
            }
        } else {
            thinkingHtml.value = '';
        }

        // Parse response part
        if (response) {
            try {
                responseHtml.value = await $markedWorker.parse(response);
            } catch (err) {
                console.error('Markdown parsing error in response block:', err);
                showError('Error rendering content. Please try again later.');
                error.value = true;
                responseHtml.value = 'Error rendering content. Please try again later.';
            }
        } else {
            responseHtml.value = '';
        }

        hasMermaid = responseHtml.value.includes('<pre class="mermaid">');

        if (hasMermaid) {
            await nextTick();
            try {
                await renderMermaidCharts();
            } catch (err) {
                console.error('Error rendering Mermaid chart:', err);
            }
        }

        return { hasMermaid };
    };

    /**
     * Parses user-provided text to extract special syntax like GitHub files.
     * @param content The raw string content from the user message.
     * @returns The cleaned content with special syntax removed.
     */
    const parseUserText = (content: string): string => {
        extractedGithubFiles.value = [];
        if (!content) return '';

        const extractRegex = /--- Start of file: (.+?) ---([\s\S]*?)--- End of file: \1 ---/g;
        const cleaned = content.replace(
            extractRegex,
            (_match, filename: string, fileContent: string) => {
                const file: FileTreeNode = {
                    name: filename.trim().split('/').pop() || '',
                    path: filename.trim(),
                    type: 'file',
                    content: fileContent.trim(),
                };
                extractedGithubFiles.value.push(file);
                return '';
            },
        );

        const nodeIdRegex = /--- Node ID: [a-f0-9-]+ ---/g;
        const cleanedWithoutNodeIds = cleaned.replace(nodeIdRegex, '');

        return cleanedWithoutNodeIds.trim();
    };

    /**
     * Splits user message content into editable zones based on Node ID markers.
     * @param content The raw string content from the user message.
     * @returns A record mapping Node IDs to their corresponding text content.
     */
    const getEditZones = (content: string): Record<string, string> => {
        const zones: Record<string, string> = {};
        if (!content) return zones;

        const nodeIdRegex = /--- Node ID: ([a-f0-9-]+) ---/g;
        let lastIndex = 0;
        let lastNodeId: string | null = null;
        let match;

        while ((match = nodeIdRegex.exec(content)) !== null) {
            const [fullMatch, nodeId] = match;
            if (lastNodeId) {
                zones[lastNodeId] = content.slice(lastIndex, match.index).trim();
            }
            lastNodeId = nodeId;
            lastIndex = match.index + fullMatch.length;
        }

        if (lastNodeId) {
            zones[lastNodeId] = content.slice(lastIndex).trim();
        }

        return zones;
    };

    return {
        thinkingHtml,
        responseHtml,
        error,
        extractedGithubFiles,
        processAssistantMessage,
        parseUserText,
        getEditZones,
    };
}
