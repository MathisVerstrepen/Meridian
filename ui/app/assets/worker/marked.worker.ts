import { Marked, type Tokens } from 'marked';
import { markedHighlight } from 'marked-highlight';
import markedKatex from 'marked-katex-extension';
import { bundledLanguages, type BundledLanguage, type Highlighter, createHighlighter } from 'shiki';
import { createOnigurumaEngine } from 'shiki/engine/oniguruma';

// --- Worker-internal state ---
const SHIKI_THEME = 'vitesse-dark';
const CORE_PRELOADED_LANGUAGES: BundledLanguage[] = [];
const MAX_CACHE_SIZE = 200;
const highlightCache = new Map<string, string>();

let markedInstancePromise: Promise<Marked> | null = null;

// --- Initialization Logic (runs inside the worker) ---

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

async function getHighlighter(): Promise<Highlighter> {
    // This is a singleton within the worker
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

                if (!Object.prototype.hasOwnProperty.call(bundledLanguages, language)) {
                    // Fallback to markdown for unknown languages
                    language = 'markdown';
                }

                const shikiLang = language as BundledLanguage;

                if (shikiLang === 'mermaid') {
                    return code;
                }

                const cacheKey = `${shikiLang}:${code}`;
                if (highlightCache.has(cacheKey)) {
                    const cachedHtml = highlightCache.get(cacheKey)!;
                    highlightCache.delete(cacheKey);
                    highlightCache.set(cacheKey, cachedHtml);
                    return cachedHtml;
                }

                try {
                    if (!loadedLangs.has(shikiLang)) {
                        await highlighter.loadLanguage(shikiLang);
                        loadedLangs.add(shikiLang);
                    }
                    const html = highlighter.codeToHtml(code, {
                        lang: shikiLang,
                        theme: SHIKI_THEME,
                        transformers: [
                            {
                                pre(node) {
                                    // Add classes for prose styling and line numbers
                                    const existingClass = (node.properties?.class as string) || '';
                                    node.properties.class = `not-prose ${existingClass} has-line-numbers replace-code-containers`;
                                },
                                line(node, line) {
                                    // Add a data-attribute to each line for the line number
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

    marked.use(markedKatex({ throwOnError: false, output: 'mathml' }));
    marked.use({ renderer: mermaidRenderer });
    return marked;
}

/**
 * Initializes the Marked instance (with plugins) and returns it.
 * This is a singleton promise to ensure initialization only happens once.
 */
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
                markedInstancePromise = null; // Allow retry on next call
                throw err;
            });
    }
    return markedInstancePromise;
}

// --- Worker Event Listener ---

/**
 * Listen for messages from the main thread.
 * A message should have a unique `id` and the `markdown` content.
 */
self.onmessage = async (event: MessageEvent<{ id: string; markdown: string }>) => {
    const { id, markdown } = event.data;

    if (!id || typeof markdown !== 'string') {
        return; // Ignore invalid messages
    }

    try {
        const marked = await getMarkedInstance();
        const html = await marked.parse(markdownPreprocessor(markdown || '')); // Ensure markdown is a string
        // Send the result back to the main thread
        self.postMessage({ id, html });
    } catch (error: unknown) {
        console.error('[Worker] Parsing failed:', error);
        // Send the error back
        self.postMessage({
            id,
            error:
                error instanceof Error
                    ? error.message
                    : 'An unknown error occurred during parsing.',
        });
    }
};
