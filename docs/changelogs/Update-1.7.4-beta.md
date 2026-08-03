# Meridian 1.7.4-beta

Meridian `1.7.4-beta` adds faster, target-aware canvas actions, reusable node presets synced through account settings, and clearer quick-workflow shortcuts. This release also keeps large preset collections contained within the settings layout.

## Highlights

### Canvas Quick Actions

A new quick-action wheel puts common canvas, node, and selection operations under the pointer while preserving familiar canvas gestures.

- Right-click the canvas, a node, or a selection to open actions for that target. Right-drag continues to start marquee selection instead of opening the wheel.
- Open and navigate the wheel from the keyboard, move through nested external rings, and keep the menu within the available viewport near screen edges.
- Canvas actions provide shortcuts to add nodes or presets, paste content, run or stop workflows, and fit the graph to view.
- Node and selection actions expose applicable quick workflows alongside directional run controls, copy, duplicate, group or unlink, delete, and stop actions.

### Account-Synced Node Presets

Reusable graph fragments can now be built in settings and placed directly from the canvas quick-action wheel.

- Create presets in a mini-canvas using prompt, file prompt, text-to-text, parallelization, routing, GitHub, context-merger, and group nodes, then connect or group them as needed.
- Rename, delete, reorder, and color-code presets from the preset rail. Invalid editor or collection state blocks settings saves until corrected.
- Place valid presets as an atomic graph fragment with fresh node and edge identities, remapped handles, centered roots, clean runtime state, and preserved plain-text groups.
- Empty or invalid presets stay out of placement menus. GitHub presets remain visibly locked when the account does not have premium access.

### Workflow and Settings Polish

Quick workflows and preset settings now communicate more with less space.

- Quick-workflow actions use configured node-type icons and colors rather than a shared generic appearance.
- Compact, category-colored input and output indicators identify prompt, context, and attachment handles while keeping workflow actions readable.
- Stable action ordering and an external quick-workflow ring make nested shortcuts easier to scan and select.
- On desktop, long preset collections scroll inside the preset rail instead of making the full settings page scroll; narrow layouts remain usable.

## Self-Hosting and Upgrade Notes

Meridian `1.7.4-beta` is a non-breaking application update with no database migration, new configuration keys, new secrets, or dependency-file changes.

- Redeploy or restart matching API and UI versions so both services use the same schema-v1 preset validation and quick-action behavior.
- Frontend Docker builds now use project-pinned pnpm through Corepack for reproducible frozen-lockfile installs.
- Existing users' settings hydrate with an empty schema-v1 preset collection by default. Presets use the existing account settings payload and persistence rather than a new table or migration.
- Preset collections support up to 8 presets per account, 20 nodes and 40 edges per preset, and 512 KiB for the complete collection.
- GitHub nodes inside presets continue to require premium access when placed; other valid preset content remains available according to the account's existing permissions.
