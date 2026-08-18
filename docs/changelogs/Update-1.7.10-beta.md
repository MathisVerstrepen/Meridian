# Meridian 1.7.10-beta

Meridian `1.7.10-beta` adds canvas graph auto layout, improves generator chain placement to reduce overlap, and tightens release changelog validation to require an exact match.

## Highlights

### Graph Auto Layout

The canvas now supports automatic arrangement of graph nodes with a deterministic, multi-strategy layout.

- Use **Auto layout** from the canvas toolbar (`Controls` top-left) or from the quick-action wheel (right-click / `Shift+F10` on the canvas). The toolbar control is disabled when the graph is empty; the wheel action appears alongside **Fit graph**.
- Layout normalizes grouped nodes to their outer container, deduplicates constraints, splits disconnected components, and arranges each component with layered strategies for vertical ranking, branch columns, attachment stacks, fanout hierarchy, and serial prompt spines before packing components into rows.
- Running auto layout repositions nodes via `@dagrejs/dagre` (`network-simplex` ranking, `greedy` acyclicer), fits the viewport (`maxZoom: 1`, `minZoom: 0.4`, `padding: 0.2`), and persists the new positions through the existing graph save path. Layout anchoring preserves the previous minimum `x`/`y` so the graph remains in its existing coordinate context, with positions rounded to whole pixels.

### Smarter Generator Chain Placement

Creating generator nodes from an existing generator parent now avoids stacking directly below the parent when a chain already exists.

- Applies to chat actions that create `text-to-text`, `parallelization`, and `routing` nodes and to quick-workflow creation when `category` is `CONTEXT`, `direction` is `source`, and the target block is a generator type.
- When the parent is a generator (`text-to-text`, `parallelization`, `routing`) and has directly-connected generator children, the new node is placed to the right of the rightmost child (`child.x + child.width + gap`) at the same `y`; otherwise it is placed below the parent (`parent.y + parent.height + gap`).
- Non-generator parents and all other quick-workflow directions/categories keep the original offset calculation, including `calculateQuickWorkflowPositionOffset` handling. Node dimensions are resolved from rendered dimensions, explicit width/height, style dimensions, or block `minSize`.

### Stricter Release Changelog Validation

Release publishing now requires byte-exact equality between the merged release pull request body and the versioned changelog.

- `scripts/release_automation.py` no longer normalizes `CRLF` (`\r\n`) to `LF` (`\n`) before comparison; `pull.get("body") != changelog` now fails the publish step before tag or release mutation.
- `docs/releasing.md` is updated to state that the PR body must exactly match the changelog, including trailing newline. The previous wording that treated `CRLF` and `LF` as equivalent is removed.

## Self-Hosting and Upgrade Notes

Meridian `1.7.10-beta` is a non-breaking frontend and release-tooling update with no database migration, new configuration keys, or new secrets. UI dependency manifests and lockfile are updated to include the layout engine.

- Rebuild and redeploy the UI to include `ui/package.json` addition `@dagrejs/dagre@^3.1.0` and `ui/pnpm-lock.yaml` updates. Frontend Docker builds include the new `graphAutoLayout` utilities (`graphAutoLayout.ts`, `graphAutoLayoutAttachmentStacks.ts`, `graphAutoLayoutBranchColumns.ts`, `graphAutoLayoutComponent.ts`, `graphAutoLayoutConstraints.ts`, `graphAutoLayoutFanoutHierarchy.ts`, `graphAutoLayoutSerialPrompts.ts`) and updated `graphGeometry.ts` / canvas wiring.
- Existing graphs, accounts, and server data require no migration. Auto layout is manual-only and saves through the existing `saveGraph` path; no automatic re-layout occurs on load.
- Release maintainers must preserve the generated release PR body exactly as the changelog, including line endings and final trailing newline, for publish validation to succeed. Mismatched bodies stop publication before any tag or release is written.
- No API image rebuild is required for the layout changes alone, but rebuilding all images from the same commit remains the standard deployment path.

