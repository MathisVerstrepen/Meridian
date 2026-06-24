# Meridian 1.6.8-beta

Meridian `1.6.8-beta` is focused on making settings easier to navigate and personalize. This release adds a redesigned settings page with searchable sections, a custom theme color editor, cleaner temporary-graph handling across navigation and history, local development migration helpers, and a smoother generated-image detail modal.

## Highlights

### Settings Navigation

The settings page has been reorganized into a clearer, sectioned workspace.

- Added a new main settings layout.
- Grouped settings into **Account**, **Appearance & Interface**, **AI Providers & Models**, **Workflow & Nodes**, **Files & Repositories**, and **Tools** sections.
- Split settings into focused pages for profile, security, API keys, usage, themes, canvas startup, chat display, model defaults, generation parameters, reasoning, repositories, file handling, and tool defaults.
- Added tab aliases so older or simpler settings links can route users to the matching new section.
- Added active-tab scrolling so the sidebar keeps the current settings section visible.
- Improved sidebar spacing, button states, and section icons for easier scanning.

### Settings Search

Settings can now be found directly from the settings page.

- Added a settings search experience backed by structured setting entries.
- Added searchable metadata for setting titles, groups, tabs, descriptions, keywords, and options.
- Added relevance scoring so exact title matches, title prefixes, and stronger field matches appear first.
- Added token normalization for more forgiving searches, including punctuation, accents, plurals, and partial words.
- Replaced hardcoded search terms with a reusable `settingsEntries` catalog.
- Added search result metadata so users can see where each setting lives before opening it.

### Custom Theme Colors

Appearance settings now support a user-defined color palette.

- Added a **Custom** theme option alongside Light, Standard, GitHub Dark, and OLED themes.
- Added a custom theme editor for background, surface, primary text, and secondary text colors.
- Added color pickers for each custom theme color.
- Added quick-start actions for creating a custom theme from an existing built-in theme.
- Added live preview cards for all themes, including the custom palette.
- Added local persistence for custom theme colors so the selected palette can be applied during startup.
- Added runtime CSS variable updates when custom theme colors change.
- Added backend settings defaults for custom theme colors so existing users receive a safe standard palette.

### Fix Temporary Graph Handling

Temporary graphs are now kept out of user-facing permanent graph lists more consistently.

- Excluded temporary graphs from the recent canvas section.
- Excluded temporary graphs from sidebar history and workspace graph lists.
- Excluded temporary graphs from history data helpers used by navigation components.
- Updated canvas-limit checks to count only non-temporary graphs.
- Improved temporary graph handling when navigating from the home page or graph page.

### Local Development

Backend migration commands are now available through the backend development script.

- Added `./run-dev.sh upgrade [revision]` for running Alembic upgrades, defaulting to `head`.
- Added `./run-dev.sh downgrade <revision>` for running Alembic downgrades.
- Kept `./run-dev.sh`, `./run-dev.sh dev`, and `./run-dev.sh serve` for starting the hot-reload backend server.
- Improved usage messages for invalid `run-dev.sh` arguments.
- Updated the backend README to use `./run-dev.sh upgrade` in local setup instructions.

### Image Playground

Generated-image details now behave better in constrained viewports.

- Improved generated-image detail modal scrolling.
- Adjusted modal layout constraints for better responsive behavior.
- Improved overflow handling for generation metadata and prompt details.

## Self-Hosting and Upgrade Notes

Self-hosted deployments can treat `1.6.8-beta` as a frontend and settings-schema upgrade.

- No database migration is required for this release.
- No new environment variables are required.
- No new backend or frontend dependencies are required.
- Existing users receive default custom theme colors automatically through the settings schema defaults.
- Local developers can now use `cd api && ./run-dev.sh upgrade` instead of running Alembic directly for normal migration upgrades.
