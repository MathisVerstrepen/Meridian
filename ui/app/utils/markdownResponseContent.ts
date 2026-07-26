import type { ToolCallArtifact } from '@/types/toolCall';

export type ImageGenState = {
    prompt: string;
    isGenerating: boolean;
    imageUrl?: string;
};

export type PreparedMarkdownResponseContent = {
    markdown: string;
    activeImageGenerations: ImageGenState[];
};

const SANDBOX_FILE_LINK_REGEX = /\[(.*?)\]\(sandbox-file:\/\/<?([0-9a-f-\s]{36,})>?\)/gi;
const SANDBOX_HTML_LINK_REGEX = /\[(.*?)\]\(sandbox-html:\/\/<?([0-9a-f-\s]{36,})>?\)/gi;
const VISUALISE_LINK_REGEX = /\[(.*?)\]\(visualise:\/\/<?([0-9a-f-\s]{36,})>?\)/gi;
const ASKING_USER_TAG_REGEX = /<asking_user([^>]*)>([\s\S]*?)<\/asking_user>/g;
const TOOL_CALL_ID_ATTR_REGEX = /\bid="([^"]+)"/;

const encodeHtmlAttribute = (value: string): string => {
    return value
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
};

const normalizeArtifactLinkId = (value: string): string | null => {
    const normalized = value.replace(/\s+/g, '');
    return /^[0-9a-f-]{36}$/i.test(normalized) ? normalized : null;
};

const processArtifactLinks = (
    markdown: string,
    artifactsById: Map<string, ToolCallArtifact>,
): string => {
    const downloads = markdown.replace(
        SANDBOX_FILE_LINK_REGEX,
        (match, label: string, rawFileId: string) => {
            const fileId = normalizeArtifactLinkId(rawFileId);
            if (!fileId) return match;
            const artifact = artifactsById.get(fileId);
            const resolvedLabel = label || artifact?.name || 'Download file';
            const filename = artifact?.name || label || 'download';
            return `<div class="sandbox-download-placeholder" data-file-id="${fileId}" data-label="${encodeHtmlAttribute(resolvedLabel)}" data-filename="${encodeHtmlAttribute(filename)}"></div>`;
        },
    );
    const htmlArtifacts = downloads.replace(
        SANDBOX_HTML_LINK_REGEX,
        (match, label: string, rawFileId: string) => {
            const fileId = normalizeArtifactLinkId(rawFileId);
            if (!fileId) return match;
            const artifact = artifactsById.get(fileId);
            const title = label || artifact?.name || 'Interactive result';
            const filename = artifact?.name || label || 'artifact.html';
            return `<div class="sandbox-html-placeholder" data-file-id="${fileId}" data-title="${encodeHtmlAttribute(title)}" data-filename="${encodeHtmlAttribute(filename)}"></div>`;
        },
    );
    return htmlArtifacts.replace(
        VISUALISE_LINK_REGEX,
        (match, label: string, rawFileId: string) => {
            const fileId = normalizeArtifactLinkId(rawFileId);
            if (!fileId) return match;
            const artifact = artifactsById.get(fileId);
            const caption = label || artifact?.name || 'Interactive visual';
            return `<div class="visualise-artifact-placeholder" data-file-id="${fileId}" data-caption="${encodeHtmlAttribute(caption)}"></div>`;
        },
    );
};

const processToolQuestions = (markdown: string): string => {
    return markdown.replace(ASKING_USER_TAG_REGEX, (_match, attributes: string) => {
        const toolCallId = TOOL_CALL_ID_ATTR_REGEX.exec(attributes || '')?.[1];
        return toolCallId
            ? `\n\n<div class="tool-question-placeholder" data-tool-call-id="${toolCallId}"></div>\n\n`
            : '';
    });
};

const processImageGeneration = (markdown: string): PreparedMarkdownResponseContent => {
    const activeImageGenerations: ImageGenState[] = [];
    if (markdown.includes('[IMAGE_GEN]') && !markdown.includes('[!IMAGE_GEN]')) {
        const match = markdown.match(/<generating_image(?:\s+[^>]*)?>\s*Prompt:\s*"([^"]*)"/s);
        activeImageGenerations.push({
            prompt: match?.[1] || 'Creating your image...',
            isGenerating: true,
        });
    }

    const cleaned = markdown
        .replace(/\[IMAGE_GEN\]/g, '')
        .replace(/\[!IMAGE_GEN\]/g, '')
        .replace(/<generating_image(?:\s+[^>]*)?>[\s\S]*?<\/generating_image>/g, '')
        .replace(/<generating_image_error(?:\s+[^>]*)?>[\s\S]*?<\/generating_image_error>/g, '');
    const transformed = cleaned.replace(/!\[(.*?)\]\((.*?)\)/g, (match, altText, imageUrl) => {
        const id = String(imageUrl).match(
            /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i,
        )?.[0];
        if (!id) return match;
        return `<div class="generated-image-placeholder" data-prompt="${encodeHtmlAttribute(String(altText))}" data-image-url="/api/auth/refresh/files/view/${id}"></div>`;
    });
    return { markdown: transformed, activeImageGenerations };
};

export const prepareMarkdownResponseContent = (
    markdown: string,
    artifacts: readonly ToolCallArtifact[],
): PreparedMarkdownResponseContent => {
    const imageResult = processImageGeneration(markdown);
    const artifactsById = new Map(artifacts.map((artifact) => [artifact.id, artifact]));
    return {
        markdown: processArtifactLinks(processToolQuestions(imageResult.markdown), artifactsById),
        activeImageGenerations: imageResult.activeImageGenerations,
    };
};
