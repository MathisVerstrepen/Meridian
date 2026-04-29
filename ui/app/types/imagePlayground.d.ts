export type ImagePlaygroundJobStatus =
    | 'pending'
    | 'processing'
    | 'retrying'
    | 'completed'
    | 'failed';

export interface ImageGenerationTaskPayload {
    prompt: string;
    effective_prompt: string;
    model: string;
    aspect_ratio: string;
    resolution: string;
    style_preset?: string | null;
    source_image_ids: string[];
}

export interface ImageGenerationJob {
    id: string;
    batch_id: string;
    status: ImagePlaygroundJobStatus;
    prompt: string;
    effective_prompt: string;
    model: string;
    aspect_ratio: string;
    resolution: string;
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
    status: 'pending' | 'processing' | 'completed' | 'completed_with_errors' | 'failed';
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
    prompt?: string | null;
    effective_prompt?: string | null;
    model?: string | null;
    aspect_ratio?: string | null;
    resolution?: string | null;
    style_preset?: string | null;
    source_image_ids: string[];
}

export interface GeneratedImageGalleryResponse {
    total: number;
    items: GeneratedImageGalleryItem[];
}
