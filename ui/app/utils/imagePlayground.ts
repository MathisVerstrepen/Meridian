import { IMAGE_STYLE_PRESETS } from '@/stores/imagePlayground';
import type { GeneratedImageGalleryItem } from '@/types/imagePlayground';
import type { ModelInfo } from '@/types/model';

export type AspectRatioOption = { id: string; w: number; h: number };

export const IMAGE_PLAYGROUND_ASPECT_RATIOS: AspectRatioOption[] = [
    { id: '1:1', w: 1, h: 1 },
    { id: '4:3', w: 4, h: 3 },
    { id: '16:9', w: 16, h: 9 },
    { id: '3:4', w: 3, h: 4 },
    { id: '9:16', w: 9, h: 16 },
];

export const IMAGE_PLAYGROUND_RESOLUTIONS: Array<{ id: string; pixels: string }> = [
    { id: '1K', pixels: '1024 px' },
    { id: '2K', pixels: '2048 px' },
    { id: '4K', pixels: '4096 px' },
];

export const IMAGE_PLAYGROUND_GENERATED_IMAGE_DRAG_TYPE =
    'application/x-meridian-image-playground-generated-image';

const ASPECT_RATIO_TOLERANCE = 0.02;

type StyleVisual = {
    image?: string;
    accent: string;
    description: string;
};

export const IMAGE_PLAYGROUND_STYLE_VISUALS: Record<string, StyleVisual> = {
    none: {
        accent: '#ccc5b9',
        description: 'Raw prompt',
    },
    photorealistic: {
        image: '/img/illustration/photorealistic.webp',
        accent: '#c19a3e',
        description: 'Natural light, sharp focus',
    },
    cinematic: {
        image: '/img/illustration/cinematic.webp',
        accent: '#eb5e28',
        description: 'Dramatic, film still',
    },
    anime: {
        image: '/img/illustration/anime.webp',
        accent: '#b2c7db',
        description: 'Vibrant line art',
    },
    render3d: {
        image: '/img/illustration/3d_render.webp',
        accent: '#7a8768',
        description: 'Octane, polished',
    },
    cyberpunk: {
        image: '/img/illustration/cyberpunk.webp',
        accent: '#eb5e28',
        description: 'Neon, high contrast',
    },
};

export const imagePlaygroundImageUrl = (id: string, thumbnail = false) =>
    thumbnail ? `/api/files/view/${id}?size=512x512` : `/api/files/view/${id}`;

export const imagePlaygroundDownloadUrl = (id: string) => `/api/files/view/${id}?download=1`;

const imagePlaygroundExtensionByContentType: Record<string, string> = {
    'image/jpeg': 'jpg',
    'image/png': 'png',
    'image/webp': 'webp',
    'image/gif': 'gif',
    'image/avif': 'avif',
    'video/mp4': 'mp4',
    'video/mpeg': 'mpeg',
    'video/mov': 'mov',
    'video/ogg': 'ogv',
    'video/quicktime': 'mov',
    'video/webm': 'webm',
    'video/x-m4v': 'm4v',
};

export const imagePlaygroundDownloadName = (
    item: GeneratedImageGalleryItem,
    fallbackExtension = 'png',
) => {
    const contentTypeExtension = item.content_type
        ? imagePlaygroundExtensionByContentType[item.content_type.toLowerCase().split(';')[0]?.trim() || '']
        : null;
    const existingExtension = item.name.match(/\.([a-z0-9]+)$/i)?.[1]?.toLowerCase();
    const extension = contentTypeExtension || existingExtension || fallbackExtension;

    return `${item.id}.${extension}`;
};

export const imagePlaygroundFormatDate = (value: string) =>
    new Date(value).toLocaleString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });

export const imagePlaygroundFormatBytes = (value?: number | null) => {
    if (!value) return '—';
    if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`;
    return `${(value / 1024 / 1024).toFixed(1)} MB`;
};

export const imagePlaygroundGenerationElapsedTime = (item: GeneratedImageGalleryItem) => {
    if (!item.generation_started_at || !item.generation_completed_at) return null;

    const startedAt = new Date(item.generation_started_at).getTime();
    const completedAt = new Date(item.generation_completed_at).getTime();
    const elapsedSeconds = Math.max(0, Math.round((completedAt - startedAt) / 1000));
    if (!Number.isFinite(elapsedSeconds)) return null;
    if (elapsedSeconds < 60) return `${elapsedSeconds}s`;

    const minutes = Math.floor(elapsedSeconds / 60);
    const seconds = elapsedSeconds % 60;
    if (minutes < 60) return seconds ? `${minutes}m ${seconds}s` : `${minutes}m`;

    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
    return remainingMinutes ? `${hours}h ${remainingMinutes}m` : `${hours}h`;
};

export const imagePlaygroundActualDimensions = (item: GeneratedImageGalleryItem) => {
    if (!item.actual_width || !item.actual_height) return null;
    return `${item.actual_width} × ${item.actual_height}`;
};

const aspectRatioValue = (ratio?: string | null) => {
    if (!ratio) return null;
    const [width, height] = ratio.split(':').map(Number);
    if (!width || !height) return null;
    return width / height;
};

const actualAspectRatioValue = (item: GeneratedImageGalleryItem) => {
    if (item.actual_width && item.actual_height) {
        return item.actual_width / item.actual_height;
    }
    return aspectRatioValue(item.actual_aspect_ratio);
};

export const imagePlaygroundDisplayAspectRatio = (item: GeneratedImageGalleryItem) => {
    const requestedValue = aspectRatioValue(item.aspect_ratio);
    const actualValue = actualAspectRatioValue(item);
    if (item.aspect_ratio && requestedValue && actualValue) {
        const ratioDelta = Math.abs(actualValue - requestedValue) / requestedValue;
        if (ratioDelta <= ASPECT_RATIO_TOLERANCE) return item.aspect_ratio;
    }

    return item.actual_aspect_ratio || item.aspect_ratio;
};

export const imagePlaygroundAspectStyle = (item: GeneratedImageGalleryItem) => {
    if (!item.actual_width || !item.actual_height) return {};
    return { aspectRatio: `${item.actual_width} / ${item.actual_height}` };
};

export const imagePlaygroundAspectClass = (item: GeneratedImageGalleryItem) => {
    switch (imagePlaygroundDisplayAspectRatio(item)) {
        case '16:9':
            return 'aspect-[16/9]';
        case '4:3':
            return 'aspect-[4/3]';
        case '3:4':
            return 'aspect-[3/4]';
        case '9:16':
            return 'aspect-[9/16]';
        default:
            return 'aspect-square';
    }
};

export const imagePlaygroundModelIcon = (model: ModelInfo) => {
    if (model.icon) return `models/${model.icon}`;
    if (model.provider === 'openai_codex') return 'models/openai';
    if (model.provider === 'opencode_go') return 'models/opencode';
    return `models/${model.provider}`;
};

export const imagePlaygroundStyleLabel = (stylePreset?: string | null) => {
    if (!stylePreset) return null;
    return IMAGE_STYLE_PRESETS[stylePreset]?.label || stylePreset;
};
