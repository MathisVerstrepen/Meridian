# Meridian 1.6.9-beta

Meridian `1.6.9-beta` is focused on admin operations, saved generation state, and day-to-day interface polish. This release adds richer admin user management, a new admin usage dashboard, node generation history with restore support, shared modal foundations, image playground improvements, chat message editing, safer WebSocket sending, and smoother local/self-hosted configuration.

## Highlights

### Admin User Management

Admins now have more direct control over users from the settings admin page.

- Added advanced filtering for the admin user list, including search, provider, plan, verification status, admin status, suspension status, and joined date range.
- Added validation so joined date filters cannot be submitted with the start date after the end date.
- Added per-user usage visibility for web search, link extraction, and storage usage.
- Added admin controls for updating user plan type.
- Added admin controls for granting and revoking admin privileges.
- Added safeguards that prevent revoking the current admin's own admin access or removing the last admin account.
- Added admin controls for resetting a user's metered web search or link extraction usage for the current billing period.
- Improved pagination and clear-filter behavior when admin filters change.

### User Suspension

Admins can now suspend user accounts directly from user management.

- Added user suspension fields for active status, reason, and optional expiration time.
- Added admin UI for temporary or indefinite suspensions.
- Added quick suspension durations for common windows such as 24 hours, 7 days, 30 days, and 90 days.
- Added backend validation so suspension end times must be in the future.
- Prevented admins from suspending their own account.
- Revoked existing refresh tokens when a user is suspended.
- Added suspension checks across authentication and user flows so suspended users are blocked consistently.

### Admin Usage Dashboard

The admin settings area now includes a high-level usage dashboard.

- Added dashboard metrics for users, graphs, query usage, storage, image generation, and video generation.
- Added selectable reporting windows for 7 days, 30 days, 90 days, and 1 year.
- Added media generation status breakdowns for completed, active, failed, and cancelled jobs.
- Added refresh and last-updated states for admin dashboard metrics.
- Split the admin settings section into focused user management and usage dashboard views.

### Generation History

Canvas nodes can now keep a history of generated outputs and restore earlier states.

- Added a `generation_history` database table for storing node generation snapshots.
- Added backend endpoints for listing, ensuring, fetching, and restoring generation history entries.
- Added generation history buttons to supported graph nodes.
- Added a generation history popover with timestamps, model labels, tool metadata, previews, loading states, and restore actions.
- Added backfill support so existing node data can be surfaced as history when needed.
- Added restore behavior that replaces node data and can refresh chat state after restoration.
- Added settings for maximum saved generation history entries and whether the popover closes after restore.
- Added generation history metadata to settings search.

### Shared Modals

Modal behavior is now more consistent across the interface.

- Added a reusable `UiUtilsBaseModal` component with shared overlay, panel, header, footer, sizing, and close behavior.
- Added consistent Escape-key and backdrop-close handling for supported modals.
- Added ARIA labeling support for accessible modal dialogs.
- Migrated account, file manager, prompt library, welcome, and settings modals to the shared modal structure.
- Simplified repeated modal layout and close-state logic across updated components.

### Image Playground

Image and video generation workflows received usability improvements.

- Improved the generated-image detail modal with richer metadata, model icon support, and position counters.
- Added keyboard navigation for generated-image details, including Escape to close, arrow keys to move between images, and `i` to toggle details.
- Improved responsive layout and detail-panel behavior in the image detail modal.
- Added reset actions for image compose, image edit, and video generation panes.
- Updated generated media download iconography for consistency.

### Chat and Streaming Reliability

Chat interactions are easier to revise and safer during temporary chat startup.

- Improved inline editing support for chat messages.
- Added cancel flows for edited message drafts.
- Updated message footer and markdown rendering behavior to support editing states.
- Improved WebSocket send handling so callers can detect failed sends.
- Ensured WebSocket connection readiness before sending messages in streaming and title-regeneration flows.
- Moved graph save handler setup to component mount timing to avoid lifecycle race conditions.

### Local Development

The local development startup flow is easier to run end to end.

- Updated root-level `./dev.sh` for generating frontend environment variables.
- Added frontend `.env` generation from `docker/config.local.toml` through the Docker-generated env file.
- Added validation for required Nuxt environment keys before writing the generated frontend env file.

### Self-Hosted Configuration

Admin bootstrap behavior is now configurable for self-hosted deployments.

- Added `ADMIN_USER_CREATION` configuration for controlling automatic admin assignment.
- Supported admin creation modes are no automatic admins, first configured `USERPASS` user, all configured `USERPASS` users, or every newly created account.
- Default admin bootstrap behavior remains the first configured `USERPASS` account when unset.
- Updated Docker config examples and Compose files to pass the new setting.
- Reworked configuration documentation to match the current TOML structure and clarify defaults, examples, and generated variables.

## Self-Hosting and Upgrade Notes

Self-hosted deployments should treat `1.6.9-beta` as a backend schema, admin, and frontend upgrade.

- Database migrations are required for this release.
- New migration `e2a9b7c4d5f6` adds `is_suspended`, `suspended_reason`, and `suspended_until` to `users`.
- New migration `f3a6b7c8d9e0` adds the `generation_history` table and indexes.
- Run the normal migration flow, for example `cd api && ./venv/bin/alembic upgrade head`, before starting the upgraded app.
- `ADMIN_USER_CREATION` is a new supported configuration value. Existing deployments can omit it to keep the default `first` behavior, but should add it to their TOML config when updating from the new examples.
- No new backend or frontend dependencies are required.
- Local developers can now use `./dev.sh` from the repository root to start dependencies, run migrations, generate frontend env, and launch both app servers.
