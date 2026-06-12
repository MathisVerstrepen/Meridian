import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from services.image_playground.constants import IMAGE_EDIT_PADDING_PCT, MAX_TASKS_PER_BATCH


class ImageGenerationTaskPayload(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)
    effective_prompt: Optional[str] = Field(default=None, max_length=10000)
    model: str = Field(min_length=1, max_length=255)
    aspect_ratio: str = "1:1"
    resolution: str = "1K"
    style_preset: Optional[str] = Field(default=None, max_length=64)
    source_image_ids: list[str] = Field(default_factory=list)


class CreateImageJobsPayload(BaseModel):
    tasks: list[ImageGenerationTaskPayload] = Field(min_length=1, max_length=MAX_TASKS_PER_BATCH)


class ImageEditSelectionPayload(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class ImageEditPayload(BaseModel):
    source_image_id: uuid.UUID
    prompt: str = Field(default="", max_length=8000)
    model: str = Field(min_length=1, max_length=255)
    selection: ImageEditSelectionPayload
    resolution: str = "1K"
    padding_pct: float = Field(default=IMAGE_EDIT_PADDING_PCT, ge=0, le=1)


class VideoGenerationPayload(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)
    model: str = Field(min_length=1, max_length=255)
    aspect_ratio: str = "16:9"
    resolution: str = "720p"
    duration: Optional[int] = Field(default=None, ge=1, le=60)
    generate_audio: bool = False
    source_image_ids: list[str] = Field(default_factory=list)


class CreateVideoJobsPayload(BaseModel):
    task: VideoGenerationPayload


class ImageGenerationJobResponse(BaseModel):
    id: uuid.UUID
    batch_id: uuid.UUID
    status: str
    prompt: str
    effective_prompt: str
    model: str
    media_type: str = "image"
    aspect_ratio: str
    resolution: str
    duration: Optional[int] = None
    generate_audio: bool = False
    actual_width: Optional[int]
    actual_height: Optional[int]
    actual_aspect_ratio: Optional[str]
    style_preset: Optional[str]
    source_image_ids: list[str]
    file_id: Optional[uuid.UUID]
    error: Optional[str]
    attempts: int
    max_attempts: int
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]


class CreateImageJobsResponse(BaseModel):
    job_id: uuid.UUID
    tasks: list[ImageGenerationJobResponse]


class ImageBatchStatusResponse(BaseModel):
    job_id: uuid.UUID
    status: str
    total: int
    completed: int
    failed: int
    processing: int
    pending: int
    tasks: list[ImageGenerationJobResponse]


class GeneratedImageGalleryItem(BaseModel):
    id: uuid.UUID
    name: str
    path: str
    size: Optional[int]
    content_type: Optional[str]
    created_at: datetime
    updated_at: datetime
    generation_started_at: Optional[datetime] = None
    generation_completed_at: Optional[datetime] = None
    prompt: Optional[str] = None
    effective_prompt: Optional[str] = None
    model: Optional[str] = None
    aspect_ratio: Optional[str] = None
    resolution: Optional[str] = None
    duration: Optional[int] = None
    generate_audio: Optional[bool] = None
    actual_width: Optional[int] = None
    actual_height: Optional[int] = None
    actual_aspect_ratio: Optional[str] = None
    style_preset: Optional[str] = None
    source_image_ids: list[str] = Field(default_factory=list)


class GeneratedImageGalleryResponse(BaseModel):
    total: int
    items: list[GeneratedImageGalleryItem]


class CustomImageTonePresetCreate(BaseModel):
    label: str = Field(min_length=1, max_length=48)
    suffix: str = Field(min_length=1, max_length=1200)
    description: Optional[str] = Field(default=None, max_length=80)
    image_id: Optional[uuid.UUID] = None


class CustomImageTonePresetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str
    suffix: str
    description: Optional[str]
    image_id: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime
