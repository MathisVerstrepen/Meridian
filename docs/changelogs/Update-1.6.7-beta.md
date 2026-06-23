# Meridian 1.6.7-beta

Meridian `1.6.7-beta` is focused on turning the uploads file manager into a richer workspace for organizing files and folders. This release adds move, copy, bulk actions, conflict resolution, persistent file manager preferences, improved file previews, generated-image reference dragging, a faster local development startup script, and more reliable OpenAI Codex OAuth sessions across backend workers.

## Highlights

### File Manager

The uploads file manager now behaves more like a full desktop-style file explorer.

- Added move and copy actions for files and folders.
- Added bulk delete, bulk move, and bulk copy actions for selected items.
- Added a destination folder picker for move and copy operations.
- Added drag-and-drop moving for files and folders inside the file manager.
- Added drag-selection support for selecting multiple visible files and folders.
- Added range selection with shift-click.
- Added select-all-visible and clear-selection actions.
- Added folder selection handling so folders can participate in selection and bulk operations.
- Added a richer context menu with view, move, copy, pin, unpin, and open-in-new-tab actions.
- Added multi-file download support for selected files.

### File Operation Conflict Resolution

File creation and organization workflows now have explicit conflict handling.

- Added conflict policy support for uploads, folder creation, move operations, and copy operations.
- Added conflict choices for **Replace**, **Keep both**, and **Skip**.
- Added a file conflict modal for resolving name collisions before continuing an operation.
- Added automatic duplicate-name generation for keep-both flows.
- Added backend safeguards for moving folders so folders cannot be moved into themselves or their descendants.
- Added backend safeguards for copying items so folders cannot be copied into themselves or their descendants.
- Improved replace conflict handling so existing items are removed only after the replacement operation succeeds.
- Added recursive folder copy support with storage reservation for copied files.

### Navigation, Sorting, and Filtering

The file manager now remembers more context and provides more ways to find uploads.

- Added back and forward folder navigation for the uploads tab.
- Added recent folder shortcuts.
- Added pinned folder shortcuts.
- Added persistent local storage for recent and pinned folders.
- Added sorting by name, date, size, and type.
- Added ascending and descending sort directions.
- Added a folders-first sorting option.
- Added file type filters for all files, images, PDFs, text files, and folders.
- Added search scope controls for searching the current folder or all uploads.
- Added a backend endpoint for listing all non-generated upload files and folders.

### File Manager Settings

Users can now configure default file manager behavior from settings.

- Added a default file manager sort setting.
- Added a default file manager view setting for grid, gallery, and list views.
- Added a **Remember Last Sort** setting.
- Added a **Remember Last View** setting.
- Added backend settings schema support for file manager sort and view preferences.

### Uploads and Storage Visibility

Uploading and storage management now provide more feedback.

- Added upload progress tracking for file uploads.
- Added a dedicated upload progress display with per-file status and error feedback.
- Added progress-aware upload API handling with retry support after auth refresh.
- Added a detailed storage breakdown in the file manager sidebar.
- Added categorized storage usage for generated media, artifacts, images, documents, and other upload groups.
- Added clearer near-full and full storage states.

### File Previews and Auth Refresh

File preview URLs now go through an auth-refreshing frontend proxy.

- Added a Nuxt server route for authenticated file viewing at `/api/auth/refresh/files/view/{fileId}`.
- Added transparent access-token refresh for file preview requests.
- Added range, ETag, and conditional request forwarding for proxied file views.
- Updated chat markdown, sandbox artifact previews, image generation output, and file manager previews to use the refreshed file-view route.
- Improved file preview reliability in contexts where raw bearer headers cannot be attached, such as image tags.

### Image Playground

Generated images can now be reused more directly in the Media Playground.

- Added drag-and-drop support for dragging generated gallery images into image reference slots.
- Added generated-image drag payload validation.
- Added reference drop-zone feedback in the image compose pane.
- Added a store action for adding generated images as references.
- Updated image playground uploads to use keep-both conflict handling for duplicate names.

### OpenAI Codex OAuth Reliability

OpenAI Codex device sign-in is now more reliable in multi-worker deployments.

- Added Redis-backed storage for OpenAI Codex device OAuth sessions.
- Added session serialization and deserialization for Redis storage.
- Added cross-worker OAuth completion support when Redis is available.
- Kept the existing in-memory session store as a fallback when Redis is unavailable.
- Added cleanup of Redis-backed OAuth sessions after completion.

### Local Development

Local setup is easier to start from a fresh checkout.

- Added a root-level `dev.sh` script for starting the local development stack.
- Added automatic startup for Docker-backed Postgres, Neo4j, and Redis dependencies.
- Added automatic database migration execution during local startup.
- Added backend and frontend startup with readiness checks.
- Added local development log output under `/tmp/meridian-dev`.
- Updated the README with quick-start instructions and clearer manual setup guidance.

## Self-Hosting and Upgrade Notes

Self-hosted deployments should treat `1.6.7-beta` as an application upgrade focused on file-management behavior and runtime reliability.

- Run `alembic upgrade head` as part of the normal upgrade process.
- Redis is recommended for reliable OpenAI Codex device OAuth completion across multiple backend workers.
- Deployments without Redis continue to fall back to in-memory OpenAI Codex OAuth sessions.
- The frontend now serves file previews through `/api/auth/refresh/files/view/{fileId}` so file preview requests can refresh authentication automatically.
- User settings now include file manager sort and view defaults; existing users receive schema defaults.
- The new `dev.sh` script is optional and intended for local development only.
