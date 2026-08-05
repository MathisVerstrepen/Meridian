# Releasing Meridian

Meridian releases use a manually started preparation workflow, manual CI review and merge, then automatic tag, image, and GitHub Release publication. Production deployment remains manual.

## Prerequisites

Provision the `RELEASE_TOKEN` Actions secret externally. Use an unexpired GitHub App token or fine-grained personal access token for this repository with:

- Contents: read and write
- Pull requests: read and write

Built-in `GITHUB_TOKEN` is not a supported fallback because events created with it do not reliably start the downstream PR and tag workflows. Automation does not create, rotate, or inspect this secret or alter repository settings and branch rules.

At least one existing non-`v` tag matching strict `X.Y.Z-beta` syntax must exist. Bootstrap releases are not supported. Before starting preparation, commit the next changelog to `dev` at `docs/changelogs/Update-<version>.md`. File must be non-empty UTF-8 Markdown whose first line is exactly `# Meridian <version>`.

## Prepare and merge

1. Open **Actions → Prepare Release → Run workflow** from `main`.
2. Select `patch`, `minor`, or `major`. Automation reads all strict beta tags, computes numeric successor, validates `dev` is ahead of `main`, and reads matching changelog from `dev`.
3. Inspect created or updated `dev` to `main` PR. Title must be exactly `Release Meridian <version>` and body must exactly match changelog, including trailing newline.
4. Wait for required CI to pass. Release PR image workflow runs shared lint and five parallel image builds without pushing packages. User remains responsible for CI review and manual merge.
5. Merge PR manually. Publish workflow refetches merged PR and changelog from merge commit, validates title, body, branches, repository, successor version, and tag target before writing release artifacts.

Finalization creates lightweight non-`v` `<version>` tag at merge commit and GitHub prerelease named `<version>` with exact changelog body. Tag starts five parallel publications for `frontend`, `backend`, `browser-service`, `sandbox-manager`, and `sandbox-python`. After all five exact beta images succeed, `promote-images` resolves every beta manifest before writing and repoints each corresponding GHCR `latest` alias to its resolved digest without rebuilding. `promote-release` then waits for GitHub Release availability and marks same release non-prerelease and latest. Ordinary pushes to `main` do not run image builds. Pull requests run lint and five no-push builds but never run either promotion job.

Prepare, publish, and tag workflows share repository-scoped, non-cancelling release concurrency. Pull-request image workflows remain ref-scoped and cancel superseded runs. Every tag run must be current numeric maximum among authoritative strict non-`v` `X.Y.Z-beta` GitHub tags. First check occurs in lint before beta image writes. Image promotion repeats check after all five manifest reads and immediately before first `latest` write. Release promotion checks before lookup and again immediately before Release edit. Malformed tags, stale historic reruns, missing tags, and GitHub API failures fail rather than skip promotion or move either meaning of `latest` backward.

## Failure and recovery

Failures before tag creation are fail-closed. Correct changelog, PR, branch, token, or version issue, then rerun preparation or failed publish workflow. Repeated preparation updates one matching open PR; multiple matching open PRs stop automation without mutation.

If tag already resolves to same merge commit, publish workflow can be rerun safely to create or reconcile release metadata. Partial tag-before-release failure is therefore recoverable. New releases remain prereleases until image promotion succeeds; reconciliation preserves an existing full release instead of demoting it.

Automation never moves or deletes immutable beta tags. Tag resolving to another commit requires operator investigation. Historic rerun with newer strict beta tag is intentionally stale and must not be retried expecting promotion.

Failure before image alias writes leaves all `latest` aliases unchanged. Missing or unreadable beta manifest fails during all-five prevalidation. Registry failure during write loop can leave subset of aliases updated; dependent Release promotion remains blocked and GitHub Release stays prerelease. Fix cause and rerun same-tag workflow or failed jobs to converge all five aliases. If all aliases promoted but bounded Release lookup or edit fails, ensure Release exists and rerun failed Release job. Same-tag operations are idempotent.

Workflow or script rollback prevents future automation but does not undo remote GHCR aliases or GitHub Release flags. For manual rollback, authenticate Docker Buildx and GitHub CLI, choose one known-good prior beta version, and repoint all five aliases before changing Release state:

```bash
repository="ghcr.io/<owner>/<repository>"
version="<known-good-version>"
for image in frontend backend browser-service sandbox-manager sandbox-python; do
    docker buildx imagetools create --prefer-index=false \
        --tag "$repository/$image:latest" "$repository/$image:$version"
done
gh release edit "$version" --prerelease=false --latest --repo <owner>/<repository>
```

Use lowercase `<owner>/<repository>` in GHCR references. Verify known-good manifests before rollback. If needed, separately mark failed release as prerelease. Never move or delete source beta tags, and never roll back only subset of five aliases.

## Production

Production update is separate, manually authorized operation after all five images and automated promotions succeed. Use existing deployment command and exact beta tag:

```bash
./docker/run.sh prod <version>
```

Release automation never deploys or restarts production.
