import { Marked } from 'marked';
import { markedHighlight } from 'marked-highlight';
import markedKatex from 'marked-katex-extension';
import { bundledLanguages, type BundledLanguage, type Highlighter, createHighlighter } from 'shiki';
import { createOnigurumaEngine } from 'shiki/engine/oniguruma';

const SHIKI_THEME = 'vitesse-dark';
const CORE_PRELOADED_LANGUAGES: BundledLanguage[] = [];

let highlighterInstance: Highlighter | null = null;
let highlighterPromise: Promise<Highlighter> | null = null;

/**
 * Singleton: returns the Shiki highlighter instance, creating it if necessary.
 */
async function getHighlighter(): Promise<Highlighter> {
    if (highlighterInstance) return highlighterInstance;

    if (!highlighterPromise) {
        console.log('[Marked Plugin] Creating Shiki CORE instance...');
        highlighterPromise = createHighlighter({
            themes: [SHIKI_THEME],
            langs: CORE_PRELOADED_LANGUAGES,
            engine: createOnigurumaEngine(() => import('shiki/wasm')),
        })
            .then((instance) => {
                highlighterInstance = instance;
                console.log('[Marked Plugin] Shiki CORE instance created.');
                console.log('[Marked Plugin] Loaded languages:', instance.getLoadedLanguages());
                return instance;
            })
            .catch((err) => {
                console.error('[Marked Plugin] Error creating Shiki CORE highlighter:', err);
                highlighterPromise = null;
                throw err;
            });
    }

    return highlighterPromise;
}

/**
 * Returns a configured Marked instance using Highlight and KaTeX plugins.
 */
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
                    console.warn(
                        `[Marked Plugin] Language '${language}' not recognized by Shiki. Falling back to plaintext.`,
                    );
                    return code;
                }

                const shikiLang = language as BundledLanguage;

                try {
                    if (!loadedLangs.has(shikiLang)) {
                        console.log(`[Marked Plugin] Loading language: ${shikiLang}...`);
                        await highlighter.loadLanguage(shikiLang);
                        loadedLangs.add(shikiLang);
                        console.log(`[Marked Plugin] Language ${shikiLang} loaded.`);
                    }

                    const html = highlighter.codeToHtml(code, {
                        lang: shikiLang,
                        theme: SHIKI_THEME,
                    });

                    // Ensure code blocks aren’t affected by prose stylings
                    return html.replace('<pre class=', '<pre class="not-prose');
                } catch (err) {
                    console.error(`[Marked Plugin] Highlighting error (${language}):`, err);
                    return code;
                }
            },
        }),
    );

    marked.use(
        markedKatex({
            throwOnError: true,
            output: 'mathml',
        }),
    );

    return marked;
}

/**
 * Nuxt plugin entry point.
 */
export default defineNuxtPlugin(async () => {
    try {
        const highlighter = await getHighlighter();
        const marked = await createMarkedWithPlugins(highlighter);

        return {
            provide: { marked },
        };
    } catch (error) {
        console.error('[Marked Plugin] Failed to initialize Marked with Shiki/KaTeX:', error);

        // Fallback Marked instance (no highlighting, no latex)
        const fallbackMarked = new Marked();
        return {
            provide: {
                marked: {
                    parse: (content: string) => {
                        try {
                            return fallbackMarked.parse(content ?? '') as string;
                        } catch (err) {
                            console.error('[Marked Plugin] Fallback parse error:', err);
                            return content;
                        }
                    },
                } as unknown as Marked,
            },
        };
    }
});
