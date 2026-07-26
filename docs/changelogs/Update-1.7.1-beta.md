# Meridian 1.7.1-beta

Meridian `1.7.1-beta` focuses on more reliable chat editing, faster and more stable streamed Markdown, better canvas performance on large graphs, and on-demand inspection of generated images. This release also improves sandbox previews and model-menu placement.

## Highlights

### Reliable Chat Revisions and Editing

Chat messages now retain the identities needed to render and edit the correct content as conversations change.

- Replaced broad message watching with targeted identity and text revisions, so same-length edits, message replacements, and streaming updates are detected without deeply observing every message field.
- Preserved both prompt-node and generator-node identities for newly created messages, so editing an untagged prompt updates the prompt node rather than the generator node.
- Kept compatibility with older messages that only have a generator identity, while reloaded messages with explicit node tags continue to target those tagged prompt sections.

### Faster, Declarative Markdown Rendering

Streaming responses now preserve completed content while updating only the portion that is still changing.

- Split Markdown into stable and active segments, reusing completed parsing and DOM output while reparsing only changed streaming tails or segments affected by reference-definition updates.
- Retained stable rendered blocks across stream updates and deferred Mermaid finalization until pending diagrams are ready.
- Moved generated images, tool questions, sandbox downloads and HTML previews, visualizations, code-copy controls, and Mermaid fullscreen controls into Vue-owned declarative rendering with isolated targets and cleanup.
- Added structured handling for sandbox artifacts and response markers while preserving existing streamed response behavior.

### Faster Canvas Operations

Canvas interactions now use spatial indexing to reduce unnecessary node scans on larger and more widely distributed graphs.

- Indexed compatible handles for exact nearest-handle snapping.
- Indexed overlap blockers while preserving existing placement order and attached-node movement.
- Indexed rectangle-selection candidates, including nested nodes and reverse-direction selections.
- Added sparse-grid handling for distant nodes and broad selection areas without changing boundary or tie-breaking behavior.

### On-Demand Image Inspection

Supported vision-capable chat models can now inspect generated images when image-generation tools are enabled, allowing follow-up analysis without placing image bytes in conversation history.

- Added an internal `inspect_image` tool for supported OpenRouter, Gemini CLI, OpenAI Codex, and OpenCode Go model configurations.
- Restricted inspection to user-owned, locally stored raster images and validated file identity, storage paths, declared image type, decoded dimensions, and resource limits before use.
- Downscaled and normalized inspection copies for bounded provider requests, with at most two successful inspections per tool round and inspection kept separate from interactive user questions.
- Kept image pixels transient for the immediate continuation while persisting only bounded, sanitized tool results and provenance needed to request inspection again after history reconstruction.

### Interface Polish

Focused fixes improve overlays and menus in constrained layouts.

- Updated expanded sandbox HTML previews to use the obsidian background and let embedded artifacts fill the modal without inset framing.
- Updated teleported model menus to measure their rendered height, open above the trigger when they would overflow the viewport, and reposition when the panel size changes.

## Self-Hosting and Upgrade Notes

Meridian `1.7.1-beta` is a non-breaking application update with no database migration, new configuration keys, new secrets, or dependency-file changes.

- Redeploy or restart the API and UI services to apply the chat, Markdown, canvas, model-menu, and image-inspection changes.
- Existing generated images require no migration. Inspection is available only when the selected model supports image input and Meridian tools, image generation is enabled for the chat, and the referenced file is an eligible user-owned local raster image.
- Source-development `make infra-up` now starts the existing sandbox manager alongside local Docker dependencies; no additional sandbox configuration is introduced by this release.
