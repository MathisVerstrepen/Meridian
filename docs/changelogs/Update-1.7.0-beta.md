# Meridian 1.7.0-beta

Meridian `1.7.0-beta` is focused on faster canvas workflows, more capable model and web-tool interactions, stronger account and repository security, and a safer self-hosting configuration system. This release adds configurable quick-workflow wheels, model-aware reasoning controls, compact API payloads, batched web tools backed by a private browser sidecar, Alibaba Personal Token Plan support across chat and media, image playground fixes, OpenAI Codex reliability improvements, configurable plan limits, and expanded development checks.

## Highlights

### Quick Workflows and Canvas

Canvas workflows can now create and connect common nodes more quickly while preserving existing graphs.

- Added six configurable handle wheels for quickly creating or connecting nodes from canvas handles.
- Added overlap resolution, legacy settings hydration, and repair handling for saved quick-workflow configurations.
- Added an accessible tabbed settings workbench with a reusable custom-slot editor for configuring the wheels.
- Updated context-merger targets to accept multiple incoming context edges, including when nodes are placed through snap actions.
- Prevented normal and snap placement from creating duplicate edges with the same source, source handle, target, and target handle.
- Improved GitHub icon contrast in quick-workflow wheels and settings.

### Model-Aware Reasoning and API Efficiency

Reasoning controls now adapt to each model's capabilities, while large model and graph responses use more compact transfers.

- Expanded the available reasoning-effort levels and surfaced model reasoning capabilities in the interface.
- Known unsupported reasoning efforts now resolve to the nearest supported value; ties follow `preferHigherReasoningEffort`, which defaults to `true`, while models with unknown capabilities preserve the selected effort.
- Added a versioned compact model-catalog payload that the UI decodes for lower transfer overhead.
- Added a versioned compact editor-graph response with UI validation, backup recovery, and compatibility with unversioned graph data.

### Web Search and Link Extraction

Web tools now support richer batches, clearer grouped results, and more resilient page extraction.

- Added ordered batches of one to five search queries or page URLs, with per-item results and errors and a root error when every item fails; obsolete singular inputs are rejected.
- Added grouped fetched-page summaries with favicon stacks, result totals, and matching details.
- Improved grouped search displays so query metadata and per-entry errors are retained while legacy flat results remain readable.
- Improved fetched-page selection so page index and URL identify the correct result or error even when a URL appears more than once or uses a legacy result shape.
- Added resolved navigation links from fetched pages so follow-up destinations can be explored directly from the returned Markdown.
- Added external-link favicons, non-wrapping Markdown links, and clearer inline-citation guidance.
- Simplified fetched-page labels by omitting a leading `www.` without changing destinations.
- Kept search and fetched-page disclosures closed while results are streaming and when errors occur.
- Added an authenticated private browser sidecar as a fallback when direct and ordinary-proxy extraction paths cannot fetch a page.

### Image Playground

Image editing and navigation are more reliable and responsive.

- Made provider image failures reported as HTTP 400 or 422 eligible for retry.
- Preserved both image-edit uploads when their filenames conflict.
- Limited Meridian Cloud editing to one supported source image and safely reset edit state when the source changes.
- Centered image zooming on the cursor.
- Removed transform-transition lag while panning images.
- Reduced the rendering cost of the in-progress media animation by moving its gradient with transforms instead of animating background position.

### Alibaba Personal Token Plan

Users can connect their own Alibaba Personal Token Plan key for chat, image, and video generation.

- Added provider settings for securely connecting and disconnecting a user-owned key, with the available model catalog refreshed from Alibaba's live and official sources.
- Added chat and dynamically discovered image-model support, including square 1K and 2K output with up to three reference images.
- Added HappyHorse text-to-video, image-to-video, and reference-to-video generation with model-specific reference and frame controls, 720p or 1080p output, and provider-managed audio. Other Alibaba video families, video editing, and image masks remain unsupported.

### Account, Repository, and Chat Experience

Account setup, repository handling, session security, and chat behavior received focused usability and reliability improvements.

- Updated welcome configuration links to open the API Keys settings tab directly.
- Added validation, synchronization, and local serving for provider OAuth avatars without allowing avatar-sync failures to block token flows.
- Scoped repositories and their storage paths to the authenticated owner, using isolated `{user_uuid}/{repository_local_path_uuid}` directories for every operation.
- Added locked, staged cloning with atomic promotion, credential-free stored URLs, status tracking, rate limits, and cleanup handling.
- Made refresh-token rotation atomic so only one concurrent request can consume a token and subsequent replay attempts trigger the existing theft response.
- Corrected spacing around asked-user responses in chat.
- Strengthened shared assistant guidance for response accuracy, prompt-injection resistance, language and creative behavior, and tool use.

### OpenAI Codex Reliability

OpenAI Codex conversations now preserve more complete output and handle provider failures more consistently.

- Preserved all streamed output between tool rounds and increased the continuation limit from 8 to 100 rounds.
- Improved refusal and failure handling with sanitized diagnostics and canonical output.
- Prevented expanded tool context from being duplicated across continuation rounds.

### Development and Quality

Repository workflows and automated checks are more consistent and provide better failure evidence.

- Added a unified root Makefile workflow and reorganized development and test scripts around the root commands.
- Added tagged Playwright smoke and full correctness targets, a two-worker default, and a compatibility alias for the full correctness suite.
- Added separate Vitest unit and Nuxt suites, shared graph and Markdown utilities, and integration with root test commands.
- Moved browser performance checks into an explicit serial target outside the correctness suites.
- Improved end-to-end failure evidence with page, browser-console, request-failure, trace, and related diagnostics.
- Added regression coverage for graph-chat overlap direction.
- Updated to Nuxt 4.5.0, refreshed frontend and source dependencies, and documented the supported Node.js versions.

## Self-Hosting and Upgrade Notes

Self-hosted deployments should treat `1.7.0-beta` as an immediate breaking configuration and runtime upgrade, even though it requires no database migration.

- Deployment TOML files are no longer read and have no fallback. Before updating, privately back up the old ignored TOML configuration outside the repository and inventory its settings without printing secrets.
- Run `make config-init-prod` for production or build deployments, or `make config-init-dev` for development. Put only non-secret deviations in the matching sparse `version: 1` YAML override under `docker/config/overrides/`, and put secrets only in the matching file under `docker/config/secrets/`.
- Configuration precedence is tracked common defaults, then tracked production or local profile defaults, then the sparse override. Secrets are loaded separately rather than merged into YAML.
- Required secret keys are `NUXT_SESSION_PASSWORD`, `MASTER_OPEN_ROUTER_API_KEY`, `BACKEND_SECRET`, `JWT_SECRET_KEY`, `LINK_EXTRACTION_BROWSER_SERVICE_TOKEN`, `REDIS_PASSWORD`, `POSTGRES_PASSWORD`, and `NEO4J_PASSWORD`; supply values privately in the profile secrets file and do not place them in YAML.
- The browser-service token must be independent from backend, JWT, and session secrets and contain at least 32 visible ASCII characters. After rotating it, recreate the API and browser sidecar together.
- Preflight the intended profile with `./docker/run.sh dev --config-only` or `./docker/run.sh build --config-only`. For production, include the intended release version between `prod` and `--config-only`; resolve every validation error before starting normally.
- Successful rendering atomically writes mode-`0600` outputs to `docker/env/.env.prod`, `docker/env/.env.compose.local`, or `docker/env/.env.local`, depending on the selected profile and runtime.
- Local, production, and source-build Compose flows now include the private browser sidecar. Prebuilt deployments must pull and start its image, and API link extraction falls back to it only after direct and ordinary-proxy paths fail.
- The API no longer installs the browser runtime dependencies; the separate sidecar image contains its browser stack. Source developers should run `make install` to refresh dependencies.
- The frontend now uses Nuxt 4.5.0 and supports Node.js 22.19 or newer on Node 22, 24.11 or newer on Node 24, or Node 26 and newer.
- Plan limits are now configurable with unchanged defaults: `limits.free.web_search` is `0`, `limits.free.link_extraction` is `0`, `limits.free.storage_mib` is `50`, `limits.premium.web_search` is `200`, `limits.premium.link_extraction` is `1000`, and `limits.premium.storage_mib` is `5120`.
- All six limits must be non-negative integers, and zero is allowed. Storage uses binary MiB. Limit changes require an API restart; lowering query limits does not reset current usage, and lowering storage limits does not delete files.
- Existing clones in the legacy shared `{provider}/{project_path}` layout are not adopted or removed automatically. Back them up, have each user re-clone with their current credentials, verify the new scoped clones, and remove the legacy data manually when appropriate.
- Recreate or restart every affected service after rendering configuration changes. In particular, token or browser-port changes require the API and browser sidecar to be recreated together.
- Complete rollback requires the matching previous API image, Compose definitions, and TOML-era configuration to be restored together before restarting. There is no database migration and no persisted crawler migration in this release.
