# Releasing Meridian

Meridian releases use a manually started preparation workflow, manual CI review and merge, then automatic tag, prerelease, and image publication. Production deployment remains manual.

## Prerequisites

Provision the `RELEASE_TOKEN` Actions secret externally. Use an unexpired GitHub App token or fine-grained personal access token for this repository with:

- Contents: read and write
- Pull requests: read and write

Built-in `GITHUB_TOKEN` is not a supported fallback because events created with it do not reliably start the downstream PR and tag workflows. Automation does not create, rotate, or inspect this secret or alter repository settings and branch rules.

At least one existing non-`v` tag matching strict `X.Y.Z-beta` syntax must exist. Bootstrap releases are not supported. Before starting preparation, commit the next changelog to `dev` at `docs/changelogs/Update-<version>.md`. File must be non-empty UTF-8 Markdown whose first line is exactly `# Meridian <version>`.

## Prepare and merge

1. Open **Actions → Prepare Release → Run workflow** from `main`.
2. Select `patch`, `minor`, or `major`. Automation reads all strict beta tags, computes numeric successor, validates `dev` is ahead of `main`, and reads matching changelog from `dev`.
3. Inspect created or updated `dev` to `main` PR. Title must be exactly `Release Meridian <version>` and body must match changelog. CRLF and LF line endings are equivalent; all other whitespace, including trailing newline, must match.
4. Wait for required CI to pass. Release PR image workflow runs shared lint and five parallel image builds without pushing packages. User remains responsible for CI review and manual merge.
5. Merge PR manually. Publish workflow refetches merged PR and changelog from merge commit, validates title, body, branches, repository, successor version, and tag target before writing release artifacts.

Finalization creates lightweight non-`v` `<version>` tag at merge commit and GitHub prerelease named `<version>` with exact changelog body. Tag starts five parallel publications for `frontend`, `backend`, `browser-service`, `sandbox-manager`, and `sandbox-python`. Observe all five matrix entries and verify exact beta image tags in GHCR. Ordinary pushes to `main` do not run image builds.

## Failure and recovery

Failures before tag creation are fail-closed. Correct changelog, PR, branch, token, or version issue, then rerun preparation or failed publish workflow. Repeated preparation updates one matching open PR; multiple matching open PRs stop automation without mutation.

If tag already resolves to same merge commit, publish workflow can be rerun safely to create or reconcile prerelease. Partial tag-before-release failure is therefore recoverable. Existing release metadata is restored to canonical name, body, draft status, and prerelease status.

Automation never moves or deletes tags. Tag resolving to another commit or newer strict beta tag requires operator investigation; do not retarget immutable release tag through this workflow. If image publication fails after tag creation, rerun failed image workflow for same tag rather than recreating release.

## Production

Production update is separate, manually authorized operation after all five images succeed. Use existing deployment command and exact beta tag:

```bash
./docker/run.sh prod <version>
```

Release automation never deploys or restarts production.
