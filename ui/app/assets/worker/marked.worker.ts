import { Marked, type Tokens } from 'marked';
import { markedHighlight } from 'marked-highlight';
import { bundledLanguages, type BundledLanguage, type Highlighter, createHighlighter } from 'shiki';
import { createOnigurumaEngine } from 'shiki/engine/oniguruma';
import katex from 'katex';

// --- Constants ---
const SHIKI_THEME = 'vitesse-dark';
const CORE_PRELOADED_LANGUAGES: BundledLanguage[] = [];
const MAX_CACHE_SIZE = 200;
const highlightCache = new Map<string, string>();

// --- Constants (From New Code - LaTeX System) ---
const BLOCK_MATH_PLACEHOLDER_PREFIX = '\x00BLOCK_MATH_';
const INLINE_MATH_PLACEHOLDER_PREFIX = '\x00INLINE_MATH_';
const PLACEHOLDER_SUFFIX = '\x00';

// --- Types ---
interface MathBlock {
    type: 'block' | 'inline';
    content: string;
    placeholder: string;
}

let markedInstancePromise: Promise<Marked> | null = null;

// --- Text Processing Utilities ---

// Function to process Mermaid text
const mermaidTextProcessor = (text: string): string => {
    text = text.replace(/<br\s*\/?>/gi, '<br>');
    return text;
};

// Function to preprocess markdown text before rendering
const markdownPreprocessor = (text: string): string => {
    text = text.replace(/```\nmermaid/g, '```mermaid');
    return text;
};

// --- LaTeX Processing ---

/**
 * Extracts all LaTeX math expressions from the markdown string and replaces
 * them with unique placeholders to prevent Marked from mangling them.
 */
function extractMathExpressions(markdown: string): {
    processed: string;
    mathBlocks: MathBlock[];
} {
    const mathBlocks: MathBlock[] = [];
    let processed = markdown;
    let blockIndex = 0;
    let inlineIndex = 0;

    // 1. Extract BLOCK math ($$...$$) first.
    const blockMathRegex = /\$\$([\s\S]*?)\$\$/g;
    processed = processed.replace(blockMathRegex, (_match, content: string) => {
        const placeholder = `${BLOCK_MATH_PLACEHOLDER_PREFIX}${blockIndex}${PLACEHOLDER_SUFFIX}`;
        mathBlocks.push({
            type: 'block',
            content: content.trim(),
            placeholder,
        });
        blockIndex++;
        return placeholder;
    });

    // 2. Extract INLINE math ($...$).
    const inlineMathRegex = /(?<!\\)\$([^\s$](?:[^$\n]*[^\s$])?)\$/g;
    processed = processed.replace(inlineMathRegex, (_match, content: string) => {
        const placeholder = `${INLINE_MATH_PLACEHOLDER_PREFIX}${inlineIndex}${PLACEHOLDER_SUFFIX}`;
        mathBlocks.push({
            type: 'inline',
            content: content.trim(),
            placeholder,
        });
        inlineIndex++;
        return placeholder;
    });

    return { processed, mathBlocks };
}

/**
 * Renders extracted math blocks using KaTeX and replaces the placeholders
 * in the final HTML string.
 */
function renderAndRestoreMath(html: string, mathBlocks: MathBlock[]): string {
    let result = html;

    for (const block of mathBlocks) {
        let renderedHtml: string;
        try {
            renderedHtml = katex.renderToString(block.content, {
                displayMode: block.type === 'block',
                throwOnError: false,
                output: 'html',
                strict: false,
                trust: true,
            });

            if (block.type === 'block') {
                renderedHtml = `<div class="katex-display">${renderedHtml}</div>`;
            }
        } catch (err) {
            const escaped = block.content
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');
            const wrapper = block.type === 'block' ? 'div' : 'span';
            renderedHtml = `<${wrapper} class="katex-error" title="KaTeX parsing error">${block.type === 'block' ? '$$' : '$'}${escaped}${block.type === 'block' ? '$$' : '$'}</${wrapper}>`;
            console.error('[Worker] KaTeX rendering error:', err);
        }

        const pWrapped = `<p>${block.placeholder}</p>`;
        const codeWrapped = `<code>${block.placeholder}</code>`;

        if (result.includes(pWrapped)) {
            result = result.replace(pWrapped, renderedHtml);
        } else if (result.includes(codeWrapped)) {
            result = result.replace(codeWrapped, renderedHtml);
        } else {
            result = result.replace(block.placeholder, renderedHtml);
        }
    }

    return result;
}

// --- Shiki & Marked Setup ---

async function getHighlighter(): Promise<Highlighter> {
    // Singleton with Oniguruma engine
    return createHighlighter({
        themes: [SHIKI_THEME],
        langs: CORE_PRELOADED_LANGUAGES,
        engine: createOnigurumaEngine(() => import('shiki/wasm')),
    });
}

// Custom renderer for Mermaid diagrams
const mermaidRenderer = {
    code(token: Tokens.Code): string | false {
        if (token.lang === 'mermaid') {
            const cleanedText = mermaidTextProcessor(token.text);
            return `<pre class="mermaid">${cleanedText}</pre>`;
        }
        return false; // Fall back to default rendering
    },
};

async function createMarkedWithPlugins(highlighter: Highlighter): Promise<Marked> {
    const loadedLangs = new Set<string>(highlighter.getLoadedLanguages());

    const marked = new Marked(
        {
            gfm: true,
            breaks: false,
            pedantic: false,
        },
        markedHighlight({
            async: true,
            async highlight(code: string, lang?: string) {
                let language = (lang || 'markdown').toLowerCase();

                // Fallback for unknown languages
                if (!Object.prototype.hasOwnProperty.call(bundledLanguages, language)) {
                    language = 'markdown';
                }

                const shikiLang = language as BundledLanguage;

                // Mermaid handling
                if (shikiLang === 'mermaid') {
                    return code;
                }

                // Caching Logic
                const cacheKey = `${shikiLang}:${code}`;
                if (highlightCache.has(cacheKey)) {
                    const cachedHtml = highlightCache.get(cacheKey)!;
                    highlightCache.delete(cacheKey); // LRU behavior
                    highlightCache.set(cacheKey, cachedHtml);
                    return cachedHtml;
                }

                try {
                    if (!loadedLangs.has(shikiLang)) {
                        await highlighter.loadLanguage(shikiLang);
                        loadedLangs.add(shikiLang);
                    }

                    // Transformers
                    const html = highlighter.codeToHtml(code, {
                        lang: shikiLang,
                        theme: SHIKI_THEME,
                        transformers: [
                            {
                                pre(node) {
                                    const existingClass = (node.properties?.class as string) || '';
                                    node.properties.class = `not-prose ${existingClass} has-line-numbers replace-code-containers`;
                                },
                                line(node, line) {
                                    node.properties['data-line'] = line;
                                },
                            },
                        ],
                    });

                    highlightCache.set(cacheKey, html);
                    if (highlightCache.size > MAX_CACHE_SIZE) {
                        const oldestKey = highlightCache.keys().next().value;
                        highlightCache.delete(oldestKey);
                    }

                    return html;
                } catch (err) {
                    console.error(`[Worker] Highlighting error (${language}):`, err);
                    return code;
                }
            },
        }),
    );

    marked.use({ renderer: mermaidRenderer });

    return marked;
}

function getMarkedInstance(): Promise<Marked> {
    if (!markedInstancePromise) {
        console.log('[Worker] Initializing Marked with Shiki/KaTeX...');
        markedInstancePromise = getHighlighter()
            .then(createMarkedWithPlugins)
            .then((instance) => {
                console.log('[Worker] Initialization complete.');
                return instance;
            })
            .catch((err) => {
                console.error('[Worker] Failed to initialize Marked:', err);
                markedInstancePromise = null;
                throw err;
            });
    }
    return markedInstancePromise;
}

// --- Worker Event Listener ---

self.onmessage = async (event: MessageEvent<{ id: string; markdown: string }>) => {
    const { id, markdown } = event.data;

    if (!id || typeof markdown !== 'string') {
        return;
    }

    try {
        const marked = await getMarkedInstance();

        // 1. Preprocess Markdown
        const preprocessedMarkdown = markdownPreprocessor(markdown || '');

        // 2. Extract Math
        const { processed, mathBlocks } = extractMathExpressions(preprocessedMarkdown);

        // 3. Parse via Marked
        const rawHtml = await marked.parse(processed);

        // 4. Restore Math
        const finalHtml = renderAndRestoreMath(rawHtml, mathBlocks);

        self.postMessage({ id, html: finalHtml });
    } catch (error: unknown) {
        console.error('[Worker] Parsing failed:', error);
        self.postMessage({
            id,
            error:
                error instanceof Error
                    ? error.message
                    : 'An unknown error occurred during parsing.',
        });
    }
};
