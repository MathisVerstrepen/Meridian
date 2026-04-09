import { Marked, type Tokens } from 'marked';
import { markedHighlight } from 'marked-highlight';
import type { BundledLanguage, Highlighter } from 'shiki';
import type katexType from 'katex';

// --- Constants ---
const SHIKI_THEME = 'vitesse-dark';
const CORE_PRELOADED_LANGUAGES: BundledLanguage[] = [];
const MAX_CACHE_SIZE = 200;
const highlightCache = new Map<string, string>();

// --- Placeholder Constants ---
const PLACEHOLDER_SUFFIX = '\x00';
const BLOCK_MATH_PLACEHOLDER_PREFIX = '\x00BLOCK_MATH_';
const INLINE_MATH_PLACEHOLDER_PREFIX = '\x00INLINE_MATH_';
const FENCED_CODE_PLACEHOLDER_PREFIX = '\x00FENCED_CODE_';
const INLINE_CODE_PLACEHOLDER_PREFIX = '\x00INLINE_CODE_';

// --- Types ---
interface MathBlock {
    type: 'block' | 'inline';
    content: string;
    placeholder: string;
}

interface CodeBlock {
    placeholder: string;
    original: string;
}

// --- Text Processing Utilities ---

// Function to process Mermaid text
const mermaidTextProcessor = (text: string): string => {
    text = text.replace(/<br\s*\/?>/gi, '<br>');
    return text;
};

// Function to preprocess markdown text before rendering
const markdownPreprocessor = (text: string): string => {
    if (!text.includes('```\nmermaid')) {
        return text;
    }
    text = text.replace(/```\nmermaid/g, '```mermaid');
    return text;
};

// --- Code Block Protection ---

/**
 * Extracts all code blocks (fenced and inline) from the markdown string and
 * replaces them with unique placeholders to prevent LaTeX extraction from
 * processing content inside code.
 */
function protectCodeBlocks(markdown: string): {
    processed: string;
    codeBlocks: CodeBlock[];
} {
    if (!markdown.includes('`')) {
        return {
            processed: markdown,
            codeBlocks: [],
        };
    }

    const codeBlocks: CodeBlock[] = [];
    let processed = markdown;
    let fencedIndex = 0;
    let inlineIndex = 0;

    // 1. Protect fenced code blocks (```...```) first
    // Matches opening ```, optional language identifier, content, and closing ```
    const fencedCodeRegex = /```[\s\S]*?```/g;
    processed = processed.replace(fencedCodeRegex, (match) => {
        const placeholder = `${FENCED_CODE_PLACEHOLDER_PREFIX}${fencedIndex}${PLACEHOLDER_SUFFIX}`;
        codeBlocks.push({ placeholder, original: match });
        fencedIndex++;
        return placeholder;
    });

    // 2. Protect inline code (`...`)
    // Matches single backtick, content without backticks or newlines, closing backtick
    const inlineCodeRegex = /`[^`\n]+`/g;
    processed = processed.replace(inlineCodeRegex, (match) => {
        const placeholder = `${INLINE_CODE_PLACEHOLDER_PREFIX}${inlineIndex}${PLACEHOLDER_SUFFIX}`;
        codeBlocks.push({ placeholder, original: match });
        inlineIndex++;
        return placeholder;
    });

    return { processed, codeBlocks };
}

/**
 * Restores code block placeholders back to their original content.
 */
function restoreCodeBlocks(text: string, codeBlocks: CodeBlock[]): string {
    if (!codeBlocks.length) {
        return text;
    }

    let result = text;
    for (const block of codeBlocks) {
        result = result.replaceAll(block.placeholder, block.original);
    }
    return result;
}

// --- LaTeX Processing ---

/**
 * Extracts all LaTeX math expressions from the markdown string and replaces
 * them with unique placeholders to prevent Marked from mangling them.
 */
function extractMathExpressions(markdown: string): {
    processed: string;
    mathBlocks: MathBlock[];
} {
    if (!markdown.includes('$')) {
        return {
            processed: markdown,
            mathBlocks: [],
        };
    }

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

// --- Lazy KaTeX Loading ---

let katexInstance: typeof katexType | null = null;
let katexPromise: Promise<typeof katexType> | null = null;

function getKatexLazy(): Promise<typeof katexType> {
    if (katexInstance) return Promise.resolve(katexInstance);
    if (!katexPromise) {
        katexPromise = import('katex').then((m) => {
            katexInstance = m.default;
            return katexInstance;
        }).catch((err) => {
            katexPromise = null;
            throw err;
        });
    }
    return katexPromise;
}

/**
 * Renders extracted math blocks using KaTeX and replaces the placeholders
 * in the final HTML string.
 */
async function renderAndRestoreMath(html: string, mathBlocks: MathBlock[]): Promise<string> {
    if (!mathBlocks.length) {
        return html;
    }

    const katex = await getKatexLazy();

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

        // Handle cases where Marked might wrap placeholders in <p> or <code> tags
        const pWrapped = `<p>${block.placeholder}</p>`;
        const codeWrapped = `<code>${block.placeholder}</code>`;

        if (result.includes(pWrapped)) {
            result = result.replace(pWrapped, renderedHtml);
        } else if (result.includes(codeWrapped)) {
            result = result.replace(codeWrapped, renderedHtml);
        } else {
            result = result.replaceAll(block.placeholder, renderedHtml);
        }
    }

    return result;
}

// --- Lazy Shiki Loading (deferred via dynamic import) ---

let highlighterInstance: Highlighter | null = null;
let highlighterPromise: Promise<Highlighter> | null = null;
let bundledLanguagesMap: Record<string, unknown> | null = null;
const loadedLangs = new Set<string>();

function getHighlighterLazy(): Promise<Highlighter> {
    if (highlighterInstance) return Promise.resolve(highlighterInstance);
    if (!highlighterPromise) {
        highlighterPromise = Promise.all([
            import('shiki'),
            import('shiki/engine/javascript'),
        ]).then(([shikiModule, engineModule]) => {
            bundledLanguagesMap = shikiModule.bundledLanguages;
            return shikiModule.createHighlighter({
                themes: [SHIKI_THEME],
                langs: CORE_PRELOADED_LANGUAGES,
                engine: engineModule.createJavaScriptRegexEngine(),
            });
        }).then((h) => {
            highlighterInstance = h;
            for (const lang of h.getLoadedLanguages()) {
                loadedLangs.add(lang);
            }
            return h;
        }).catch((err) => {
            highlighterPromise = null;
            throw err;
        });
    }
    return highlighterPromise;
}

// --- Marked Instances ---

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

const MARKED_BASE_OPTIONS = {
    gfm: true,
    breaks: false,
    pedantic: false,
} as const;

// Sync Marked instance — no async highlight plugin, for markdown without fenced code blocks
let markedSyncInstance: Marked | null = null;

function getMarkedSync(): Marked {
    if (markedSyncInstance) return markedSyncInstance;
    markedSyncInstance = new Marked(MARKED_BASE_OPTIONS);
    markedSyncInstance.use({ renderer: mermaidRenderer });
    return markedSyncInstance;
}

// Async Marked instance — with Shiki highlighting, for markdown with fenced code blocks
let markedAsyncInstance: Marked | null = null;

function getMarkedAsync(): Marked {
    if (markedAsyncInstance) return markedAsyncInstance;

    const marked = new Marked(
        MARKED_BASE_OPTIONS,
        markedHighlight({
            async: true,
            async highlight(code: string, lang?: string) {
                let language = (lang || 'markdown').toLowerCase();

                // Fallback for unknown languages (check after Shiki loaded)
                if (bundledLanguagesMap && !Object.prototype.hasOwnProperty.call(bundledLanguagesMap, language)) {
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
                    // Shiki is loaded lazily — only when first code block is encountered
                    const highlighter = await getHighlighterLazy();

                    // Re-check language validity now that bundledLanguages is available
                    if (bundledLanguagesMap && !Object.prototype.hasOwnProperty.call(bundledLanguagesMap, language)) {
                        language = 'markdown';
                    }
                    const resolvedLang = language as BundledLanguage;

                    if (!loadedLangs.has(resolvedLang)) {
                        await highlighter.loadLanguage(resolvedLang);
                        loadedLangs.add(resolvedLang);
                    }

                    // Transformers
                    const html = highlighter.codeToHtml(code, {
                        lang: resolvedLang,
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
    markedAsyncInstance = marked;

    return marked;
}

// --- Worker Event Listener ---

self.onmessage = async (event: MessageEvent<{ id: string; markdown: string }>) => {
    const { id, markdown } = event.data;

    if (!id || typeof markdown !== 'string') {
        return;
    }

    try {
        // 1. Preprocess Markdown
        const preprocessedMarkdown = markdownPreprocessor(markdown || '');

        const hasFencedCode = preprocessedMarkdown.includes('```');
        const hasDollarSign = preprocessedMarkdown.includes('$');

        let markdownForParse: string;
        let mathBlocks: MathBlock[] = [];

        if (hasDollarSign) {
            // Has LaTeX — need code block protection to prevent $ inside code from being extracted
            const { processed: codeProtected, codeBlocks } = protectCodeBlocks(preprocessedMarkdown);
            const extracted = extractMathExpressions(codeProtected);
            markdownForParse = restoreCodeBlocks(extracted.processed, codeBlocks);
            mathBlocks = extracted.mathBlocks;
        } else {
            // No LaTeX — skip code block protection entirely
            markdownForParse = preprocessedMarkdown;
        }

        // Use sync Marked when no fenced code blocks (avoids async overhead + Shiki loading)
        let rawHtml: string;
        if (hasFencedCode) {
            rawHtml = await getMarkedAsync().parse(markdownForParse);
        } else {
            rawHtml = getMarkedSync().parse(markdownForParse) as string;
        }

        // Restore Math in the final HTML
        const finalHtml = await renderAndRestoreMath(rawHtml, mathBlocks);

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
