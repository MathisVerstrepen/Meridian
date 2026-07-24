import { createApp, defineAsyncComponent, h, type App, type Ref } from 'vue';
import GeneratedImageCard from '~/components/ui/chat/utils/generatedImageCard.vue';
import SandboxArtifactDownload from '~/components/ui/chat/utils/sandboxArtifactDownload.vue';
import ToolQuestionCard from '~/components/ui/chat/utils/toolQuestionCard.vue';
import CodeBlockCopyButton from '~/components/ui/chat/utils/copyButton.vue';
import { decorateExternalLinkFavicons } from '~/utils/externalLinkFavicons';

const FullScreenButton = defineAsyncComponent(
    () => import('~/components/ui/chat/utils/fullScreenButton.vue'),
);

type OpenLightbox = (payload: { src: string; prompt: string }) => void;

type EnhancementOptions = {
    contentRef: Ref<HTMLElement | null>;
    renderMermaidCharts: (selector?: string) => Promise<void>;
    openLightbox: OpenLightbox;
};

const escapeAttributeValue = (value: string): string =>
    value.replace(/\\/g, '\\\\').replace(/"/g, '\\"');

export const useMarkdownDomEnhancements = ({
    contentRef,
    renderMermaidCharts,
    openLightbox,
}: EnhancementOptions) => {
    const ownedApps = new Map<string, App[]>();
    const pendingMermaidKeys = new Set<string>();

    const getRoot = (renderKey: string): HTMLElement | null => {
        const container = contentRef.value;
        if (!container) return null;
        return Array.from(
            container.querySelectorAll<HTMLElement>('[data-markdown-segment-key]'),
        ).find((root) => root.dataset.markdownSegmentKey === renderKey) ?? null;
    };

    const trackApp = (renderKey: string, app: App) => {
        const apps = ownedApps.get(renderKey) ?? [];
        apps.push(app);
        ownedApps.set(renderKey, apps);
    };

    const mountCodeCopyButtons = (renderKey: string, root: HTMLElement) => {
        const codeBlocks = Array.from(root.querySelectorAll('pre')).filter((pre) =>
            pre.querySelector('pre.replace-code-containers'),
        );
        for (const pre of codeBlocks) {
            if (pre.parentElement?.classList.contains('code-wrapper')) continue;
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
            trackApp(renderKey, app);
        }
    };

    const mountGeneratedImages = (renderKey: string, root: HTMLElement) => {
        for (const placeholder of root.querySelectorAll<HTMLElement>(
            '.generated-image-placeholder',
        )) {
            const { prompt, imageUrl } = placeholder.dataset;
            if (!prompt || !imageUrl) continue;
            const wrapper = document.createElement('div');
            placeholder.replaceChildren(wrapper);
            const app = createApp({
                render: () =>
                    h(GeneratedImageCard, {
                        prompt,
                        imageUrl,
                        onOpenLightbox: openLightbox,
                    }),
            });
            app.mount(wrapper);
            trackApp(renderKey, app);
        }
    };

    const mountSandboxDownloads = (renderKey: string, root: HTMLElement) => {
        for (const placeholder of root.querySelectorAll<HTMLElement>(
            '.sandbox-download-placeholder',
        )) {
            const { fileId, label, filename } = placeholder.dataset;
            if (!fileId || !label) continue;
            const wrapper = document.createElement('div');
            placeholder.replaceChildren(wrapper);
            const app = createApp({
                render: () =>
                    h(SandboxArtifactDownload, {
                        fileId,
                        label,
                        filename: filename || label,
                        compact: true,
                    }),
            });
            app.mount(wrapper);
            trackApp(renderKey, app);
        }
    };

    const mountToolQuestions = (renderKey: string, root: HTMLElement) => {
        for (const placeholder of root.querySelectorAll<HTMLElement>(
            '.tool-question-placeholder',
        )) {
            const { toolCallId } = placeholder.dataset;
            if (!toolCallId) continue;
            const wrapper = document.createElement('div');
            placeholder.replaceChildren(wrapper);
            const app = createApp({
                render: () => h(ToolQuestionCard, { toolCallId }),
            });
            app.mount(wrapper);
            trackApp(renderKey, app);
        }
    };

    const mountMermaidFullscreen = (
        renderKey: string,
        root: HTMLElement,
        rawMermaidElements: string[],
    ) => {
        const mermaidBlocks = Array.from(root.querySelectorAll('pre.mermaid'));
        mermaidBlocks.forEach((block, index) => {
            if (block.parentElement?.classList.contains('mermaid-wrapper')) return;
            const wrapper = document.createElement('div');
            wrapper.classList.add('mermaid-wrapper', 'relative');
            block.parentElement?.insertBefore(wrapper, block);
            wrapper.appendChild(block);
            const mountNode = document.createElement('div');
            const app = createApp(FullScreenButton, {
                renderedElement: block.cloneNode(true),
                rawMermaidElement: rawMermaidElements[index] || '',
                class: 'hover:bg-stone-gray/20 bg-stone-gray/10 absolute top-2 right-2 h-8 w-8 p-1 backdrop-blur-sm',
            });
            app.mount(mountNode);
            wrapper.appendChild(mountNode);
            trackApp(renderKey, app);
        });
    };

    const finalizeMermaid = async (renderKeys?: Iterable<string>): Promise<number> => {
        const keys = new Set(renderKeys ?? pendingMermaidKeys);
        const roots = [...keys]
            .map((key) => ({ key, root: getRoot(key) }))
            .filter((entry): entry is { key: string; root: HTMLElement } => entry.root !== null)
            .filter((entry) => entry.root.querySelector('pre.mermaid') !== null);
        if (!roots.length) {
            for (const key of keys) pendingMermaidKeys.delete(key);
            return 0;
        }

        const rawByKey = new Map(
            roots.map(({ key, root }) => [
                key,
                Array.from(root.querySelectorAll('pre.mermaid')).map((block) => block.innerHTML),
            ]),
        );
        const selector = roots
            .map(
                ({ key }) =>
                    `[data-markdown-segment-key="${escapeAttributeValue(key)}"] pre.mermaid`,
            )
            .join(',');
        await renderMermaidCharts(selector);
        for (const { key, root } of roots) {
            if (getRoot(key) !== root) {
                pendingMermaidKeys.delete(key);
                continue;
            }
            mountMermaidFullscreen(key, root, rawByKey.get(key) ?? []);
            pendingMermaidKeys.delete(key);
        }
        return roots.length;
    };

    const enhance = async (renderKeys: Iterable<string>, _isStreaming: boolean): Promise<number> => {
        let enhancedCount = 0;
        for (const renderKey of renderKeys) {
            const root = getRoot(renderKey);
            if (!root) continue;
            decorateExternalLinkFavicons(root);
            mountCodeCopyButtons(renderKey, root);
            mountGeneratedImages(renderKey, root);
            mountSandboxDownloads(renderKey, root);
            mountToolQuestions(renderKey, root);
            if (root.querySelector('pre.mermaid')) {
                pendingMermaidKeys.add(renderKey);
            }
            enhancedCount += 1;
        }
        return enhancedCount;
    };

    const dispose = (renderKeys: Iterable<string>) => {
        for (const renderKey of renderKeys) {
            for (const app of ownedApps.get(renderKey) ?? []) app.unmount();
            ownedApps.delete(renderKey);
            pendingMermaidKeys.delete(renderKey);
        }
    };

    const disposeAll = () => {
        dispose([...new Set([...ownedApps.keys(), ...pendingMermaidKeys])]);
    };

    return {
        enhance,
        finalizePendingMermaid: () => finalizeMermaid(),
        dispose,
        disposeAll,
    };
};
