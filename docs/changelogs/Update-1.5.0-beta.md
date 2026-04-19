# Meridian 1.5.0-beta

Meridian `1.5.0-beta` is a large pre-release focused on subscription-backed model access, a rebuilt model selection flow, richer usage visibility, and better runtime support for provider-native coding agents.

## Highlights

### Subscription Inference Providers

Meridian can now work with multiple subscription-backed provider runtimes alongside metered OpenRouter models.

- Added support for **Claude Agent**, **GitHub Copilot**, **Z.AI Coding Plan**, **Gemini CLI**, **OpenAI Codex**, and **OpenCode Go**.
- Added a new **Account Providers** settings tab for connecting and disconnecting provider credentials from the UI.
- Subscription models now carry richer metadata, including billing type, connection requirements, and Meridian tool compatibility.
- Available subscription models refresh automatically after provider credentials are added or removed.

### Model Selector Redesign

The model dropdown has been redesigned to work well with a much broader catalog.

- Split the dropdown into **Pinned Models**, per-provider subscription sections, and **All Models** for metered entries.
- Added section metadata, jump navigation, and virtualization for smoother browsing across large model lists.
- Added better pinned-model handling, including keyboard shortcut support.
- Added warning labels when a model does not support native JSON output.

### Usage Data and Cost Visibility

Usage reporting is now much more detailed, especially for multi-request and tool-heavy runs.

- Added normalized usage aggregation with request-level breakdowns.
- Added `cost_details` support so upstream inference cost components can be shown explicitly.
- Added per-tool usage tracking for subscription providers.
- Redesigned the usage popover to show totals, individual request passes, and parallelization model breakdowns in a clearer way.
- Improved finish-reason and tool-name visibility inside usage details.

### Tooling Across Providers

Subscription providers now integrate more deeply with Meridian's tool system.

- Added Meridian tool support across subscription-backed providers for **web search**, **link extraction**, **code execution**, **image generation**, **Visualise**, and **Ask User**.
- Added a provider-aware image generation service path instead of routing everything through the older shared flow.
- Improved tool runtime registration and summary rendering for richer provider-native tool call output.
- Added tool call duration tracking and chat display for faster debugging and better user feedback.

### Ask User and Chat Resume Improvements

User-interruptible tool flows are more resilient and easier to continue.

- Added local draft persistence for pending tool questions so answers survive refreshes and accidental navigation.
- Improved resume behavior after submitting tool responses.
- Added better handling for pending tool call IDs across backend services and frontend components.

### Canvas and Navigation

- Added a quick-create flow that places new graphs directly inside the currently selected folder or workspace from the home page.
- Improved recent-canvas and sidebar history interactions for folder-heavy workspaces.
- Fixed routing node execution issues.
- Improved parallelization and text-to-text node behavior around cancellation and stream state handling.

## Self-Hosting and Upgrade Notes

Self-hosted deployments should treat `1.5.0-beta` as an upgrade that adds new runtime requirements.

- Run `alembic upgrade head`. This release adds a migration for tool call duration tracking.
- Backend environments now need **Node.js** and **npm** available for the bundled **Gemini CLI** and **OpenAI Codex** bridge runtimes.
- Local installs should also install the runtime package dependencies in `api/app/gemini_cli_runtime` and `api/app/openai_codex_runtime`.
- Users who want subscription-backed model access must connect provider credentials from **Settings -> Account -> Providers**.
