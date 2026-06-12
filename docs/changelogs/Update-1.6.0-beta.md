# Meridian 1.6.0-beta

Meridian `1.6.0-beta` introduces the new **Media Playground**, a dedicated workspace for generating, editing, organizing, and reusing AI-generated images and videos. This release adds a full media-generation backend, real-time job tracking, provider-aware image/video model selection, custom tone presets, and a richer gallery experience.

## Highlights

### Media Playground

Meridian now includes a dedicated creative workspace at `/images/playground`.

- Added a new **Media playground** entry point from the home page.
- Added three playground modes: **Image generation**, **Image edit**, and **Video generation**.
- Added a darkroom-style full-screen interface with drag-and-drop and clipboard image support.
- Added URL-based mode switching so playground modes can be linked directly.
- Added shared source/reference image handling across image and video workflows.

### Image Generation

The playground can now generate images directly from prompts using compatible image models.

- Added multi-model image generation so users can run the same prompt across several models at once.
- Added batch generation support with up to **24 tasks per batch** and up to **4 parallel generations**.
- Added configurable image aspect ratios: `1:1`, `16:9`, `4:3`, `3:4`, and `9:16`.
- Added configurable image resolutions: `1K`, `2K`, and `4K`.
- Added an iteration slider for generating multiple variations per selected model.
- Added reference image support through upload, paste, drag-and-drop, and existing cloud files.
- Added drag-and-drop reordering for source/reference images.
- Added structured effective prompts with user prompt, style metadata, and ratio metadata.
- Added prompt history with local persistence for recently used image prompts.
- Added image model search inside the playground model selector.
- Added loading skeletons and improved empty/loading states for model selection.

### Tone and Style Presets

Image generation now supports built-in and user-created tone presets.

- Added built-in image tone presets for **Photorealistic**, **Cinematic**, **Anime**, **3D Render**, and **Cyberpunk**.
- Added support for custom tone presets with a name, prompt suffix, description, and optional preview image.
- Added backend persistence for custom image tone presets.
- Added API endpoints for listing and creating custom tone presets.
- Added tone preview support in the generation flow.
- Added custom tone presets to the image playground store so presets can be reused across sessions.

### Image Editing

The Media Playground adds an image editing flow for targeted AI edits and inpainting-style changes.

- Added an **Image edit** mode for modifying selected regions of an existing image.
- Added image upload and source-image selection for editing.
- Added a canvas selection tool with resizable edit rectangles.
- Added configurable context padding around the selected edit region.
- Added smart edit prompt construction for remove, replace, add, and style-transfer edits.
- Added scene analysis for lighting, color temperature, texture, perspective, and noise profile.
- Added mask analysis so edits can better preserve selection boundaries.
- Added advanced compositing with image alignment, color transfer, and blending for more natural edits.
- Added before/after review for edited images.

### Video Generation

Meridian can now generate videos from prompts and optional image references.

- Added a **Video generation** mode to the playground.
- Added OpenRouter-backed video generation support.
- Added async video generation jobs using the same job system as image generation.
- Added configurable video aspect ratios: `16:9`, `9:16`, `1:1`, `4:3`, `3:4`, `21:9`, and `9:21`.
- Added configurable video resolutions: `480p`, `720p`, `1080p`, `1K`, `2K`, and `4K`.
- Added duration controls with automatic duration support.
- Added optional audio generation for video jobs.
- Added reference image support for video generation.
- Added a video gallery with playback and generated-video metadata.
- Added a default video model setting, defaulting to `google/veo-3.1`.

### Gallery and Media Management

Generated media now has a dedicated gallery with search, filters, details, and reuse actions.

- Added an image gallery for generated images.
- Added infinite scrolling for generated image browsing.
- Added gallery search by prompt/model metadata.
- Added filters for model, aspect ratio, and whether an image used references.
- Added an image detail modal with prompt, model, dimensions, aspect ratio, style, references, and generation timing.
- Added previous/next navigation inside the image detail modal.
- Added actions to download, reuse settings, copy prompts, and delete generated media.
- Added generated-image dimension measurement and display.
- Added dynamic download filenames based on generated file IDs and content type.
- Improved file serving so generated/reference images can open inline while downloads still use stable filenames.

### Real-Time Job Tracking

Image and video generation now run through a persisted job system with real-time status updates.

- Added the `image_generation_jobs` database table for image and video generation tasks.
- Added persisted job state for prompt, effective prompt, model, media type, status, attempts, source images, dimensions, duration, audio flag, and completion timestamps.
- Added real-time job updates over WebSocket using `image_generation_job_update` messages.
- Added active job hydration so the UI can recover running jobs after refresh.
- Added polling fallback and periodic active-job synchronization.
- Added an active jobs lane showing pending, processing, retrying, failed, cancelled, and completed work.
- Added batch status aggregation with `pending`, `processing`, `completed`, `completed_with_errors`, `failed`, and `cancelled` states.
- Added cancellation for active jobs.
- Added retry support for failed jobs.
- Added dismiss and clear-failed actions for failed jobs.
- Added retry handling for rate limits, transient provider errors, empty image results, and Codex auth failures.
- Added clearer user-facing error messages for provider failures.

### Provider and Model Support

Media generation now understands model output modalities and uses provider-specific generation paths.

- Added a provider image/video generation service shared by playground and tool flows.
- Added OpenRouter image generation through the chat completions image modality.
- Added OpenRouter video generation through the video generation API with polling and media download.
- Added OpenAI Codex image generation support when Codex credentials are connected.
- Added model filtering by output modality so image and video selectors show compatible models only.
- Added output modality metadata handling for OpenRouter models.
- Updated the OpenRouter frontend model catalog URL to the current catalog endpoint.
- Fixed image model pricing handling when image pricing is `0`.
- Added brand icon aliases and SVG icons for Flux and Sourceful models.
- Added visual handling for image/video-capable models in selection flows.

### Tools and Chat Integration

The existing image generation tool path now shares more of the new media-generation infrastructure.

- Added shared helpers for building image content payloads with reference images.
- Added shared helpers for building video reference payloads.
- Added a `generate_video` tool definition and runtime registration.
- Added video-generation model settings for graph/tool use.
- Added node-level support for selecting image and video generation models.
- Improved generated image card rendering in chat.
- Improved markdown rendering for generated media output.

### Settings

Media generation settings now cover both image and video defaults.

- Added **Default Image Model** filtering so only image-capable models appear.
- Added **Default Video Model** setting for video-capable models.
- Added `defaultVideoModel` to image generation tool settings.
- Improved playground startup so default models wait for settings/model readiness before being applied.

## Backend Changes

- Added a new `/images` FastAPI router.
- Added endpoints for image jobs, video jobs, image editing, galleries, active jobs, retries, cancellation, failed-job cleanup, and tone presets.
- Added new schemas in `api/app/schemas/images.py`.
- Added a new `api/app/services/image_playground/` service package.
- Added provider-level image/video generation in `api/app/services/provider_image_generation.py`.
- Added generated media persistence helpers.
- Added provider error classification for retryable and user-actionable failures.
- Added gallery query services for generated images and videos.
- Added tone preset services.
- Added `numpy` and `opencv-python-headless` backend dependencies for image edit processing.

## Frontend Changes

- Added the new `/images/playground` Nuxt page.
- Added dedicated playground components for the header, image compose pane, image edit pane, video pane, gallery pane, gallery tiles, active jobs lane, drag overlay, and image detail modal.
- Added a new `imagePlayground` Pinia store.
- Added frontend API methods for all new media endpoints.
- Added playground-specific TypeScript DTOs.
- Added media utility helpers for URLs, download names, metadata formatting, model icons, aspect ratio display, and elapsed generation time.
- Added playground-specific CSS for the darkroom layout, scrollbars, loading states, sliders, modal transitions, and generation animations.

## Testing

- Added backend tests for image edit processing.
- Added backend tests for generated media file creation and dimension handling.
- Added backend tests for image playground gallery mapping.
- Added backend tests for image generation job status and WebSocket updates.
- Added backend tests for provider error classification.
- Added backend tests for provider image/video generation behavior.
- Added OpenRouter tests for output modalities and image pricing behavior.

## Self-Hosting and Upgrade Notes

Self-hosted deployments should treat `1.6.0-beta` as a database and dependency upgrade.

- Run `alembic upgrade head`.
- This release adds the `image_generation_jobs` table.
- This release adds image job fields for actual dimensions, media type, video duration, and audio generation.
- This release adds the `custom_image_tone_presets` table.
- Reinstall backend Python dependencies so `numpy` and `opencv-python-headless` are available.
- OpenRouter credentials are required for OpenRouter-backed image and video generation.
- Video generation currently requires OpenRouter video-capable models.
- OpenAI Codex image generation requires connected Codex credentials.
- Generated images and videos are stored in Meridian file storage and count as user-owned generated media.
