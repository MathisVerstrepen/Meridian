import { Marked } from 'marked';
import { markedHighlight } from 'marked-highlight';
import markedKatex from 'marked-katex-extension';
import { bundledLanguages, type BundledLanguage, type Highlighter, createHighlighter } from 'shiki';
import { createOnigurumaEngine } from 'shiki/engine/oniguruma';

// --- Worker-internal state ---
const SHIKI_THEME = 'vitesse-dark';
const CORE_PRELOADED_LANGUAGES: BundledLanguage[] = [];

let markedInstancePromise: Promise<Marked> | null = null;

// --- Initialization Logic (runs inside the worker) ---

async function getHighlighter(): Promise<Highlighter> {
    // This is a singleton within the worker
    return createHighlighter({
        themes: [SHIKI_THEME],
        langs: CORE_PRELOADED_LANGUAGES,
        engine: createOnigurumaEngine(() => import('shiki/wasm')),
    });
}

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
                const language = (lang || 'plaintext').toLowerCase();

                if (!Object.prototype.hasOwnProperty.call(bundledLanguages, language)) {
                    // Don't warn in worker, just fallback
                    return code;
                }

                const shikiLang = language as BundledLanguage;

                try {
                    if (!loadedLangs.has(shikiLang)) {
                        await highlighter.loadLanguage(shikiLang);
                        loadedLangs.add(shikiLang);
                    }
                    const html = highlighter.codeToHtml(code, {
                        lang: shikiLang,
                        theme: SHIKI_THEME,
                    });
                    return html.replace('<pre class=', '<pre class="not-prose');
                } catch (err) {
                    console.error(`[Worker] Highlighting error (${language}):`, err);
                    return code;
                }
            },
        }),
    );

    marked.use(markedKatex({ throwOnError: false, output: 'mathml' }));
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
        const html = await marked.parse(markdown || ''); // Ensure markdown is a string
        // Send the result back to the main thread
        self.postMessage({ id, html });
    } catch (error: any) {
        console.error('[Worker] Parsing failed:', error);
        // Send the error back
        self.postMessage({
            id,
            error: error.message || 'An unknown error occurred during parsing.',
        });
    }
};
