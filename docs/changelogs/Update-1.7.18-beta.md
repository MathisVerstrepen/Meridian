# Meridian 1.7.18-beta

Meridian `1.7.18-beta` improves OpenCode Go conversation routing and provider credential validation, restores backdrop blur in production builds, and refreshes frontend, browser, and provider runtime dependencies.

## Highlights

### More Reliable OpenCode Go Sessions

- Send a stable session header across conversation turns, model changes, title generation, and tool rounds to keep provider routing consistent.
- Derive conversation session identifiers from hashed user and graph identifiers instead of sending those local identifiers directly. Validation and graph-less requests use fresh session identifiers.
- Validate subscription credentials against current models on the matching inference endpoint. Try another model only when the provider explicitly reports that a validation model is unavailable; other failures stop validation with an error.

### Better OpenAI Codex Credential Checks

- Probe current Codex models with bounded fallbacks instead of relying on one hardcoded model being available to every account.
- Distinguish permission failures from invalid authentication, and report when no validation model is available to the account.
- Require an explicit completed response so truncated streams and mid-stream errors cannot incorrectly validate a session.

### Production UI Fixes

- Preserve backdrop blur on the model selector and generation history popover after production CSS minification.
- Normalize default tool selections when creating graph blocks.

### Updated Dependencies and Runtime Builds

- Upgrade Nuxt to 4.6, Mermaid to 12, and refresh Vue, Pinia, Markdown rendering, syntax highlighting, and frontend development dependencies.
- Refresh Gemini CLI, OpenAI Codex, Claude Agent, and GitHub Copilot runtime dependencies, with Gemini model resolution adapted to the updated SDK exports.
- Upgrade browser-service dependencies and the pinned Camoufox browser, and adapt web extraction and Reddit conversion to the updated Markdown conversion library.
- Use Node.js 24 in the API image and lockfile-based `npm ci` installs for its JavaScript runtimes. Add Mermaid parsing and provider import smoke checks during image builds.

## Self-Hosting and Upgrade Notes

Meridian `1.7.18-beta` introduces no database migrations, new configuration keys, or new secrets. Existing stored data requires no conversion.

- Rebuild and redeploy matching frontend, API, and browser-service images to apply the UI, provider, and runtime changes.
- Source installations should refresh dependencies from the committed manifests and lockfiles. Frontend development uses the project-pinned pnpm 12.14 through Corepack; build permissions and overrides now live in `ui/pnpm-workspace.yaml`.
- Frontend and standalone Mermaid runtimes require Node.js 22.12 or newer. The API Docker image supplies Node.js 24.
- Keep the generated release PR body byte-identical to this changelog, including line endings and the trailing newline. Review CI and merge manually; release automation does not deploy or restart production services.
