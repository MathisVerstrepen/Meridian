# Meridian 1.7.9-beta

Meridian `1.7.9-beta` turns the homepage version into a complete release-notes viewer, adds a browser-local update indicator, and tightens release changelog validation during publishing.

## Highlights

### Homepage Release Notes

The homepage version now opens the complete repository changelog catalog without a runtime API request.

- Select the version display to open formatted release notes for every changelog under `docs/changelogs`, ordered by numeric release version from newest to oldest.
- Switch between releases inside a responsive modal; the newest release is selected again whenever the modal opens.
- Changelogs are loaded and rendered during the Nuxt build, with embedded raw HTML escaped before the generated content reaches the browser.

### Browser-Local Update Indicator

The version display now shows when the loaded release is newer than the release last viewed in the current browser.

- A first visit with a valid beta version shows an update indicator. Opening release notes immediately clears it and stores the current version under `meridian-last-seen-release`.
- Older stored versions restore the indicator, while equal or newer stored versions do not. Viewing a rolled-back build preserves the newer watermark.
- Development or malformed version values do not create a release watermark, and unavailable browser storage does not prevent release notes from opening.

### Exact Release Changelog Validation

Release publishing now rejects a release pull request when its body differs from the merged changelog.

- Pull request bodies must exactly match the changelog, including line endings and the trailing newline.
- A mismatch stops publishing before tag or release mutation begins.

## Self-Hosting and Upgrade Notes

Meridian `1.7.9-beta` is a non-breaking frontend and release-tooling update with no database migration, new configuration keys, new secrets, dependency-manifest changes, or lockfile changes.

- Rebuild and redeploy the UI to include the build-time changelog catalog and homepage release-notes viewer. Frontend Docker builds now copy `docs/changelogs` into the builder before Nuxt compilation.
- Existing accounts and server data require no migration. Seen-release state remains browser-local in `localStorage` and is not synchronized through an account or backend service.
- Release maintainers using custom pull request preparation must preserve the changelog body exactly, including line endings and the final newline, for publish validation to succeed.
