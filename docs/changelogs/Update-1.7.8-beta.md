# Meridian 1.7.8-beta

Meridian `1.7.8-beta` makes release publication more conservative by limiting concurrent container builds and requiring the merged release pull request body to match its changelog exactly.

## Highlights

### Controlled Container Build Concurrency

Release and pull-request image workflows now reduce simultaneous build and registry activity while retaining the existing five-image matrix.

- The `frontend`, `backend`, `browser-service`, `sandbox-manager`, and `sandbox-python` matrix runs no more than two image builds at once.
- Matrix failures remain independent because fail-fast behavior is still disabled, while image promotion continues to wait for every build to succeed.

### Exact Release Changelog Validation

Release finalization now treats the merged pull request body and versioned changelog as one exact publication record.

- Publication stops before tag or release mutation when pull request body content differs from the merged changelog, including line endings or trailing newline.
- Release preparation therefore requires generated pull request body to remain unchanged through manual review and merge.

## Self-Hosting and Upgrade Notes

Meridian `1.7.8-beta` changes release automation only. It introduces no application runtime changes, database migrations, configuration keys, secrets, dependency changes, or data-format changes.

- Existing self-hosted deployments require no migration or configuration update for this release.
- Repository operators should preserve release pull request body exactly as generated from changelog, including final trailing newline.
- Docker publication still builds all five versioned images and promotes them only after successful completion; builds are now scheduled at most two concurrently.
- Deploying `1.7.8-beta` images remains a manual production action and uses existing self-hosting workflow; no automatic deployment or service restart is added.
