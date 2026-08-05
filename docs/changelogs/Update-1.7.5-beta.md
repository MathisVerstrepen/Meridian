# Meridian 1.7.5-beta

Meridian `1.7.5-beta` brings repository context directly into chat, adds faster image previews, and records chat-generated media in the image playground. This release also improves multi-worker coordination, GitHub Copilot runtime cleanup, and beta release operations.

## Highlights

### Repository Context in Chat

Chat prompts can now include selected repository files, issues, and pull requests without first configuring a GitHub node on the canvas.

- Open repository context from the chat add menu, choose the files or issues and pull requests tab, and review the selected repository, branch, and item counts before sending.
- Search available repositories and switch between connected GitHub and GitLab providers in the new repository picker.
- Sending a prompt with repository context creates a populated context node alongside the prompt and any file-attachment nodes, preserving the selected branch and items in the graph.
- Manual chat generation now opens the upcoming node settings before creating the next generator, so model and node options are available at the expected point in the workflow.

### Attachment and Image Previews

Images are easier to identify before sending and faster to browse in generated-media galleries.

- Chat image attachments render as thumbnail tiles with accessible remove controls, while non-image files remain in a separate compact row.
- Pasted images use keep-both upload handling, so sequential clipboard images with the same original filename remain attached as distinct files.
- File previews are generated on demand as cached WebP images at fixed `48x48`, `160x160`, or `512x512` sizes; full downloads continue to use the original file.
- Image playground galleries use responsive `160x160` and `512x512` previews, while compose, detail, and video-reference thumbnails use fixed `160x160` previews. Full downloads and original-media paths continue to request original files.

### Completed Generation History

Images and videos created through chat generation tools now carry the completed-job metadata used by the image playground.

- Successful tool generations record prompt, resolved model, media type, requested aspect ratio and resolution, source-image references, and completion timestamps.
- Image records also include measured dimensions and actual aspect ratio; video records retain requested duration and audio-generation choice.
- Generated media can therefore appear in the existing playground gallery with metadata available for inspection and settings reuse.

### Distributed API Coordination

API instances now coordinate more runtime state through the existing Redis service.

- Rate limits use shared Redis-backed storage instead of process-local memory, using the configured Redis host, port, and password.
- Model discovery caches, including per-user available models and subscription-provider catalogs, are shared through Redis with bounded expiry and invalidated after provider credential changes.
- WebSocket user events and generation-task cancellation requests fan out through Redis so connections and tasks owned by another API worker can receive the relevant update.
- Redis cache failures fall back to fresh model loading, and WebSocket publishing still attempts local delivery while broker listeners reconnect after interruption.

### GitHub Copilot Runtime Cleanup

GitHub Copilot integration now uses the current SDK lifecycle and more deliberate process cleanup.

- `github-copilot-sdk` is upgraded from `0.2.3` to `1.0.8`.
- Model-list and chat sessions use scoped runtime environments, bounded session and client shutdown, force-stop fallback, and cleanup of remaining scoped Copilot processes.
- Runtime heartbeat and temporary-directory cleanup now run even when session startup, execution, or cancellation fails.

## Self-Hosting and Upgrade Notes

Meridian `1.7.5-beta` requires no database migration and adds no application configuration keys. Existing Redis settings are reused for rate limits, model caches, and WebSocket fanout; these are expanded uses of the configured Redis service, not new Redis configuration.

- Redeploy or restart matching API and UI versions to apply the chat context, preview, generation metadata, Redis coordination, and Copilot lifecycle changes.
- Reinstall backend dependencies or rebuild the backend image to apply the `github-copilot-sdk` upgrade from `0.2.3` to `1.0.8`.
- Host-development API startup now loads `docker/env/.env.local` before importing the application, ensuring existing Redis settings are available when the rate limiter is initialized.
- Maintainers using the new release workflows must provision a repository Actions secret named `RELEASE_TOKEN` with repository contents and pull-request read/write access. This secret is only for release preparation and publishing; application deployments do not consume it.
- Release preparation is now a manual workflow that validates the next changelog and creates or updates a `dev`-to-`main` release pull request. Merging that trusted release pull request creates the strict non-`v` beta tag and GitHub prerelease.
- Docker image publication now runs from strict `X.Y.Z-beta` tags for frontend, backend, browser service, sandbox manager, and sandbox Python images. Release pull requests build the same matrix without pushing, ordinary pushes to `main` no longer publish images, and production deployment remains a separate manual step.
