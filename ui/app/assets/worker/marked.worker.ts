import { Marked } from 'marked';
import { markedHighlight } from 'marked-highlight';
import { bundledLanguages, createHighlighter, type Highlighter } from 'shiki';
import katex from 'katex';

// --- Constants ---
const BLOCK_MATH_PLACEHOLDER_PREFIX = '\x00BLOCK_MATH_';
const INLINE_MATH_PLACEHOLDER_PREFIX = '\x00INLINE_MATH_';
const PLACEHOLDER_SUFFIX = '\x00';

// --- Types ---
interface MathBlock {
    type: 'block' | 'inline';
    content: string;
    placeholder: string;
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
    const mathBlocks: MathBlock[] = [];
    let processed = markdown;
    let blockIndex = 0;
    let inlineIndex = 0;

    // 1. Extract BLOCK math ($$...$$) first.
    // This regex handles $$ even when indented or spanning multiple lines.
    // It's non-greedy to correctly match the nearest closing $$.
    const blockMathRegex = /\$\$([\s\S]*?)\$\$/g;
    processed = processed.replace(blockMathRegex, (_match, content: string) => {
        const placeholder = `${BLOCK_MATH_PLACEHOLDER_PREFIX}${blockIndex}${PLACEHOLDER_SUFFIX}`;
        mathBlocks.push({
            type: 'block',
            content: content.trim(),
            placeholder,
        });
        blockIndex++;
        // Replace in-place without adding newlines to preserve list structure.
        return placeholder;
    });

    // 2. Extract INLINE math ($...$).
    // This regex matches content between single $, excluding newlines.
    // Uses negative lookbehind to avoid matching escaped \$.
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
            // On KaTeX error, display the original LaTeX in a styled error block.
            const escaped = block.content
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');
            const wrapper = block.type === 'block' ? 'div' : 'span';
            renderedHtml = `<${wrapper} class="katex-error" title="KaTeX parsing error">${block.type === 'block' ? '$$' : '$'}${escaped}${block.type === 'block' ? '$$' : '$'}</${wrapper}>`;
            console.error('[Worker] KaTeX rendering error:', err);
        }

        // Handle various wrapping scenarios Marked might produce:
        // 1. Wrapped in <p>...</p> (standalone block)
        // 2. Wrapped in <code>...</code> (if Marked mistakenly thought it was inline code)
        // 3. Plain placeholder (within lists, etc.)

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

// --- HTML Escaping Utility ---
function escapeHtml(text: string): string {
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// --- Shiki Highlighter Setup ---
let highlighter: Highlighter | null = null;

async function getHighlighter(): Promise<Highlighter> {
    if (!highlighter) {
        highlighter = await createHighlighter({
            themes: ['github-dark-default'],
            langs: Object.keys(bundledLanguages),
        });
    }
    return highlighter;
}

// --- Marked Instance Setup ---
async function createMarkedInstance(): Promise<Marked> {
    const hl = await getHighlighter();

    const marked = new Marked(
        markedHighlight({
            async: true,
            highlight: (code, lang) => {
                // Mermaid blocks should NOT be syntax highlighted.
                // Return raw code; it will be handled specially in the renderer.
                if (lang === 'mermaid') {
                    return code;
                }

                const language = hl.getLoadedLanguages().includes(lang) ? lang : 'plaintext';
                return hl.codeToHtml(code, {
                    lang: language,
                    theme: 'github-dark-default',
                });
            },
        }),
    );

    marked.setOptions({
        gfm: true,
        breaks: false,
    });

    // Custom renderer for code blocks
    const renderer = {
        code(token: { text: string; lang?: string; escaped?: boolean }): string {
            // Handle Mermaid blocks - wrap in <pre class="mermaid"> for later rendering
            // by the useMermaid composable.
            if (token.lang === 'mermaid') {
                // Escape HTML to prevent XSS. Mermaid reads textContent which auto-decodes.
                const escapedCode = escapeHtml(token.text);
                return `<pre class="mermaid">${escapedCode}</pre>`;
            }

            // For all other code blocks, token.text contains Shiki's HTML output.
            // Inject a marker class for the useMarkdownProcessor enhancer.
            const shikiHtml = token.text;
            return shikiHtml.replace('<pre ', '<pre class="replace-code-containers" ');
        },
    };

    marked.use({ renderer });

    return marked;
}

let markedInstance: Marked | null = null;

async function getMarkedInstance(): Promise<Marked> {
    if (!markedInstance) {
        markedInstance = await createMarkedInstance();
    }
    return markedInstance;
}

// --- Worker Message Handler ---
self.onmessage = async (event: MessageEvent<{ id: string; markdown: string }>) => {
    const { id, markdown } = event.data;

    try {
        const marked = await getMarkedInstance();

        // Step 1: Extract all math expressions before Marked processes the text.
        const { processed, mathBlocks } = extractMathExpressions(markdown);

        // Step 2: Parse the sanitized markdown with Marked.
        const rawHtml = await marked.parse(processed);

        // Step 3: Render math and replace placeholders in the final HTML.
        const finalHtml = renderAndRestoreMath(rawHtml, mathBlocks);

        self.postMessage({ id, html: finalHtml });
    } catch (err) {
        const message = err instanceof Error ? err.message : 'Unknown parsing error';
        console.error('[Worker] Parsing failed:', err);
        self.postMessage({ id, error: message });
    }
};
