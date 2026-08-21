import type {
    MarkdownResponseRenderToken,
    PreparedMarkdownResponse,
} from '@/types/markdownRenderToken';
import { decorateExternalLinkFavicons } from '@/utils/externalLinkFavicons';

const SPECIAL_SELECTOR = [
    '.generated-image-placeholder',
    '.tool-question-placeholder',
    '.sandbox-download-placeholder',
    '.sandbox-html-placeholder',
    '.visualise-artifact-placeholder',
    'pre',
].join(',');

type MarkdownResponseTokenInput = MarkdownResponseRenderToken extends infer Token
    ? Token extends MarkdownResponseRenderToken
        ? Omit<Token, 'key' | 'targetId'>
        : never
    : never;

const safeScope = (scope: string): string => scope.replace(/[^a-zA-Z0-9_-]/g, '-');

export const prepareMarkdownResponse = (
    html: string,
    targetScope: string,
): PreparedMarkdownResponse => {
    const template = document.createElement('template');
    template.innerHTML = html;
    const root = template.content;
    const tokens: MarkdownResponseRenderToken[] = [];
    decorateExternalLinkFavicons(root);

    const createTarget = (kind: MarkdownResponseRenderToken['kind']): HTMLDivElement => {
        const index = tokens.length;
        const target = document.createElement('div');
        target.id = `markdown-token-${safeScope(targetScope)}-${index}`;
        target.dataset.markdownTokenTarget = kind;
        return target;
    };
    const addToken = (
        target: HTMLDivElement,
        token: MarkdownResponseTokenInput,
    ): void => {
        const renderToken = {
            ...token,
            key: `${targetScope}:${tokens.length}`,
            targetId: target.id,
        } satisfies MarkdownResponseRenderToken;
        tokens.push(Object.freeze(renderToken));
    };

    for (const node of Array.from(root.querySelectorAll<HTMLElement>(SPECIAL_SELECTOR))) {
        if (node.matches('.generated-image-placeholder')) {
            const { prompt, imageUrl } = node.dataset;
            if (!prompt || !imageUrl) continue;
            const target = createTarget('generated-image');
            addToken(target, { kind: 'generated-image', prompt, imageUrl });
            node.replaceWith(target);
            continue;
        }
        if (node.matches('.tool-question-placeholder')) {
            const { toolCallId } = node.dataset;
            if (!toolCallId) continue;
            const target = createTarget('tool-question');
            addToken(target, { kind: 'tool-question', toolCallId });
            node.replaceWith(target);
            continue;
        }
        if (node.matches('.sandbox-download-placeholder')) {
            const { fileId, label, filename } = node.dataset;
            if (!fileId || !label) continue;
            const target = createTarget('sandbox-download');
            addToken(target, {
                kind: 'sandbox-download',
                fileId,
                label,
                filename: filename || label,
            });
            node.replaceWith(target);
            continue;
        }
        if (node.matches('.sandbox-html-placeholder')) {
            const { fileId, title, filename } = node.dataset;
            if (!fileId) continue;
            const target = createTarget('sandbox-html');
            addToken(target, {
                kind: 'sandbox-html',
                fileId,
                title: title?.trim() || 'Interactive result',
                filename: filename?.trim() || 'artifact.html',
            });
            node.replaceWith(target);
            continue;
        }
        if (node.matches('.visualise-artifact-placeholder')) {
            const { fileId, caption } = node.dataset;
            if (!fileId) continue;
            const target = createTarget('visualise');
            addToken(target, {
                kind: 'visualise',
                fileId,
                caption: caption?.trim() || 'Interactive visual',
            });
            node.replaceWith(target);
            continue;
        }
        if (node.matches('pre.mermaid')) {
            if (node.parentElement?.classList.contains('mermaid-wrapper')) continue;
            const wrapper = document.createElement('div');
            wrapper.classList.add('mermaid-wrapper', 'relative');
            const target = createTarget('mermaid-fullscreen');
            addToken(target, { kind: 'mermaid-fullscreen', rawMermaidElement: node.innerHTML });
            node.replaceWith(wrapper);
            wrapper.append(node, target);
            continue;
        }
        if (node.matches('pre') && node.querySelector('pre.replace-code-containers')) {
            if (node.parentElement?.classList.contains('code-wrapper')) continue;
            const wrapper = document.createElement('div');
            wrapper.classList.add('code-wrapper', 'relative');
            node.classList.add(
                'overflow-x-auto',
                'rounded-lg',
                'custom_scroll',
                'bg-[#121212]',
            );
            const target = createTarget('code-copy');
            addToken(target, {
                kind: 'code-copy',
                textToCopy: node.innerText || node.textContent || '',
            });
            node.replaceWith(wrapper);
            wrapper.append(node, target);
        }
    }

    return Object.freeze({
        html: template.innerHTML,
        tokens: Object.freeze(tokens),
    });
};
