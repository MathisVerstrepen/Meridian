# Meridian 1.7.7-beta

Meridian `1.7.7-beta` automates promotion of successful beta releases across GitHub Container Registry and GitHub Releases. This release also prevents stale release runs from moving `latest` back to an older version.

## Highlights

### Automatic Image and Release Promotion

Successful strict beta-tag builds now promote the complete release without rebuilding its images.

- After all five versioned images build and publish successfully, the `frontend`, `backend`, `browser-service`, `sandbox-manager`, and `sandbox-python` manifests are resolved before their GHCR `latest` aliases are updated.
- Each `latest` alias is created from the corresponding versioned manifest digest, avoiding another image build.
- GitHub Release promotion runs only after every image alias succeeds, then marks the same release non-prerelease and latest after a bounded availability check.

### Safer Release Ordering and Recovery

Release automation now fails closed when a run is no longer eligible to publish the newest release.

- Strict non-`v` beta tags are compared numerically before image builds, immediately before image alias updates, and again before GitHub Release promotion. Historic runs fail when a newer strict beta tag exists.
- Release and beta-tag workflows share non-cancelling repository-level serialization, while pull requests retain ref-scoped cancellation, linting, and five no-push image builds without promotion.
- Re-running publication preserves an already promoted full release instead of changing it back to a prerelease.

## Self-Hosting and Upgrade Notes

Meridian `1.7.7-beta` changes release automation only. It has no application runtime changes, database migration, new configuration key, new secret, or dependency-file change.

- No data migration or application configuration action is required. Production deployment remains manual with `./docker/run.sh prod 1.7.7-beta`; release automation does not deploy or restart services.
- For repositories using this release workflow, successful beta publication now updates all five GHCR `latest` aliases and then promotes the matching GitHub Release automatically. Pull-request builds never push or promote images.
- Missing or unreadable versioned manifests stop promotion before any alias changes. A registry failure during alias updates can leave a subset changed, blocks GitHub Release promotion, and should be recovered by rerunning the same eligible tag after fixing the cause.
- If image aliases succeed but GitHub Release lookup or editing fails, the images remain promoted while the release remains a prerelease; ensure the release exists and rerun the failed release-promotion job.
- Rolling back workflow code does not restore remote image aliases or release flags. Operators must repoint all five `latest` aliases to one known-good beta version and then mark that version's GitHub Release latest.
