export type ImagePlaygroundJobStatus =
    | 'pending'
    | 'processing'
    | 'retrying'
    | 'completed'
    | 'failed'
    | 'cancelled';

export interface ImageGenerationTaskPayload {
    prompt: string;
    effective_prompt: string;
    model: string;
    aspect_ratio: string;
    resolution: string;
    style_preset?: string | null;
    source_image_ids: string[];
}

export type ImagePlaygroundMediaType = 'image' | 'video';

export interface ImageGenerationJob {
    id: string;
    batch_id: string;
    status: ImagePlaygroundJobStatus;
    prompt: string;
    effective_prompt: string;
    model: string;
    media_type: ImagePlaygroundMediaType;
    aspect_ratio: string;
    resolution: string;
    duration?: number | null;
    generate_audio: boolean;
    actual_width?: number | null;
    actual_height?: number | null;
    actual_aspect_ratio?: string | null;
    style_preset?: string | null;
    source_image_ids: string[];
    file_id?: string | null;
    error?: string | null;
    attempts: number;
    max_attempts: number;
    created_at: string;
    updated_at: string;
    completed_at?: string | null;
}

export interface CreateImageJobsResponse {
    job_id: string;
    tasks: ImageGenerationJob[];
}

export interface ImageBatchStatusResponse {
    job_id: string;
    status: 'pending' | 'processing' | 'completed' | 'completed_with_errors' | 'failed' | 'cancelled';
    total: number;
    completed: number;
    failed: number;
    processing: number;
    pending: number;
    tasks: ImageGenerationJob[];
}

export interface GeneratedImageGalleryItem {
    id: string;
    name: string;
    path: string;
    size?: number | null;
    content_type?: string | null;
    created_at: string;
    updated_at: string;
    generation_started_at?: string | null;
    generation_completed_at?: string | null;
    prompt?: string | null;
    effective_prompt?: string | null;
    model?: string | null;
    aspect_ratio?: string | null;
    resolution?: string | null;
    duration?: number | null;
    generate_audio?: boolean | null;
    actual_width?: number | null;
    actual_height?: number | null;
    actual_aspect_ratio?: string | null;
    style_preset?: string | null;
    source_image_ids: string[];
}

export interface GeneratedImageGalleryResponse {
    total: number;
    items: GeneratedImageGalleryItem[];
}

export interface ImageEditSelectionPayload {
    x: number;
    y: number;
    width: number;
    height: number;
}

export interface ImageEditPayload {
    source_image_id: string;
    prompt: string;
    model: string;
    selection: ImageEditSelectionPayload;
    resolution: string;
    padding_pct: number;
}

export interface VideoGenerationPayload {
    prompt: string;
    model: string;
    aspect_ratio: string;
    resolution: string;
    duration?: number | null;
    generate_audio: boolean;
    source_image_ids: string[];
}

export type ImageGalleryReferenceFilter = 'all' | 'with' | 'without';

export interface ImageGalleryFilters {
    search?: string;
    model?: string;
    aspect_ratio?: string;
    references?: ImageGalleryReferenceFilter;
}
