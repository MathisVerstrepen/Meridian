# Meridian 1.4.0

Meridian `1.4.0` is a feature-heavy update centered on better prompt authoring, a more capable tool runtime, stronger chat rendering, and a broad round of reliability and security hardening across the stack.

## Highlights

### Prompt Improver

Meridian now includes a dedicated **Prompt Improver** workflow for prompt nodes.

- Audit an existing prompt and score it across structured improvement dimensions.
- Select recommended dimensions or choose your own optimization focus areas.
- Let the optimizer ask clarification questions before rewriting when more context is needed.
- Review suggested changes one by one, accept or reject them, then apply the improved prompt back to the graph.
- Re-open past improvement runs from node history.
- Override the optimizer model globally in settings or select a different optimizer model directly from the Prompt Improver dialog.

### New Tool Runtime

The tool system has been expanded substantially.

- Added sandboxed **Python code execution** with bounded resources, artifact persistence, and inline chat rendering for generated files.
- Added the **Visualise** tool for Mermaid, SVG, and HTML outputs.
- Added structured **Ask User** tool support so a model can pause, ask a clarifying question, and continue after the user replies.
- Added persistent tool call storage and richer formatted tool call detail views in chat.
- Added per-tool and per-node configuration for visual generation behavior and model selection.

### Chat, Markdown, and Mermaid

Rendering and chat ergonomics received a large pass.

- Markdown processing is more resilient around tool output, artifact links, and mixed structured content.
- Mermaid rendering now supports validation and optional retry flows when generated syntax is invalid.
- Mermaid runtime loading was streamlined to reduce unnecessary upfront cost.
- Assistant message copy now excludes tool call noise.

### Canvas and Navigation

- Added graph loading and error states for a safer graph-opening flow.
- Added custom `401`, `403`, `404`, and `500` error pages.
- Improved edge compatibility and snapping on the graph canvas.
- Added pagination for graph history and recent-canvas loading, which improves responsiveness on larger workspaces.
- Continued UI cleanup, including canonical Tailwind class migration and removal of obsolete graph UI pieces.

## Fixes and Hardening

### Security and Provider Safety

- Enforced repository path restrictions under the clone root.
- Enforced SSH host key verification for GitLab clones.
- Stopped leaking Git credentials through URLs and telemetry.
- Fixed OpenRouter auth header reuse across requests.
- Improved shared HTTP client behavior and non-git HTTP/2 handling.

### Reliability and Correctness

- File uploads no longer materialize the full payload in memory before processing.
- Account deletion now removes on-disk data correctly.
- Rate limiting was rewired correctly.
- Startup and shutdown lifecycle handling now tracks cron tasks correctly.
- Canvas persistence now updates PostgreSQL and Neo4j more consistently.
- Fixed inconsistent GitLab behavior, including multi-instance handling.
- Fixed canvas backup import when `workspace_id` is missing.
- Fixed file upload node refresh behavior in the graph after attachment changes.
- Fixed several chat resume and user-awaiting state edge cases.
- Tightened validation around file-view query parameters.

## Self-Hosting and Upgrade Notes

Self-hosted deployments should treat `1.4.0` as an upgrade that requires both config and infrastructure updates.

- Update your Docker configuration. `1.4.0` introduces a dedicated `sandbox_manager` service and a new `[sandbox]` config section.
- Code execution and generated artifact workflows depend on the sandbox manager and its worker image.
