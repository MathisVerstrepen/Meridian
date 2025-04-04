import { Marked } from 'marked';
import { markedHighlight } from 'marked-highlight';

import {
    bundledLanguages,
    type BundledLanguage,
    type Highlighter,
    createHighlighter,
} from 'shiki';
import { createOnigurumaEngine } from 'shiki/engine/oniguruma';

const CORE_PRELOADED_LANGUAGES: BundledLanguage[] = [];

const SHIKI_THEME = 'vitesse-dark';

let highlighterInstance: Highlighter | null = null;
let highlighterPromise: Promise<Highlighter> | null = null;

async function getHighlighterInstance(): Promise<Highlighter> {
    if (highlighterInstance) {
        return highlighterInstance;
    }
    if (!highlighterPromise) {
        console.log('[Marked Plugin] Creating Shiki CORE instance...');
        highlighterPromise = createHighlighter({
            themes: [SHIKI_THEME],
            langs: CORE_PRELOADED_LANGUAGES,
            engine: createOnigurumaEngine(() => import('shiki/wasm')),
        })
            .then((instance) => {
                console.log('[Marked Plugin] Shiki CORE instance created.');
                highlighterInstance = instance;
                console.log(
                    '[Marked Plugin] Initially loaded languages:',
                    instance.getLoadedLanguages(),
                );
                return instance;
            })
            .catch((err) => {
                console.error(
                    '[Marked Plugin] Error creating Shiki CORE highlighter:',
                    err,
                );
                highlighterPromise = null;
                throw err;
            });
    }
    return highlighterPromise;
}

export default defineNuxtPlugin(async () => {
    try {
        const highlighter = await getHighlighterInstance();

        const runtimeLoadedLanguages = new Set<string>(
            highlighter.getLoadedLanguages(),
        );

        const marked = new Marked(
            {
                gfm: true,
                breaks: false,
                pedantic: false,
            },
            markedHighlight({
                async: true,
                async highlight(code, lang) {
                    const language = (lang || 'plaintext').toLowerCase();

                    const isValidLang = Object.prototype.hasOwnProperty.call(
                        bundledLanguages,
                        language,
                    );

                    if (!isValidLang) {
                        console.warn(
                            `[Marked Plugin] Language '${language}' is not recognized by Shiki. Falling back to plaintext.`,
                        );
                        return code;
                    }

                    const shikiLang = language as BundledLanguage;

                    try {
                        if (!runtimeLoadedLanguages.has(shikiLang)) {
                            console.log(
                                `[Marked Plugin] Attempting to dynamically load language: ${shikiLang} from CDN...`,
                            );
                            await highlighter.loadLanguage(shikiLang);
                            runtimeLoadedLanguages.add(shikiLang);
                            console.log(
                                `[Marked Plugin] Language ${shikiLang} loaded successfully.`,
                            );
                        }

                        const html = highlighter.codeToHtml(code, {
                            lang: shikiLang,
                            theme: SHIKI_THEME,
                        });

                        return html.replace(
                            '<pre class=',
                            '<pre class="not-prose',
                        );
                    } catch (error) {
                        console.error(
                            `[Marked Plugin] Error during highlighting or dynamic loading (lang: ${language}):`,
                            error,
                        );
                        return code;
                    }
                },
            }),
        );

        return {
            provide: {
                marked: marked,
            },
        };
    } catch (error) {
        console.error(
            '[Marked Plugin] Failed to initialize Marked plugin with Shiki Core:',
            error,
        );
        const fallbackMarked = new Marked();
        return {
            provide: {
                marked: {
                    parse: (content: string) => {
                        try {
                            return fallbackMarked.parse(
                                content ?? '',
                            ) as string;
                        } catch (parseError) {
                            console.error(
                                'Fallback Marked parse error:',
                                parseError,
                            );
                            return content;
                        }
                    },
                } as unknown as Marked,
            },
        };
    }
});
