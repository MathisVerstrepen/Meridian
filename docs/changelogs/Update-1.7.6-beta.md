# Meridian 1.7.6-beta

Meridian `1.7.6-beta` delivers a security-focused dependency refresh across the UI, standalone Mermaid renderer, Gemini CLI runtime, and Python development tooling. This release does not change user-visible application behavior.

## Highlights

### Security Dependency Refresh

Dependency manifests and lockfiles now resolve updated packages across affected JavaScript and Python development environments while preserving existing application behavior.

- Refreshed UI and standalone Mermaid renderer dependencies, including the workspace-level resolution used by UI installs.
- Updated Gemini CLI runtime transitive dependencies while retaining npm as its existing installation path and removing unused pnpm lock and workspace files.
- Updated Python development tooling to Black 26.3.1 and pytest 9.0.3.

## Self-Hosting and Upgrade Notes

Meridian `1.7.6-beta` has no database migration, new runtime configuration key, or new secret. API and UI images must be rebuilt and redeployed so updated dependency trees are installed.

- Rebuild and redeploy both API and UI images; dependency-only changes affect packages installed in each image.
- UI Docker dependency stages now copy the pnpm workspace manifest before frozen installs so container builds use the same dependency resolution as other UI installs.
- Developers should reinstall development dependencies to use Black 26.3.1 and pytest 9.0.3.
