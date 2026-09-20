# Meridian 1.7.16-beta

Meridian `1.7.16-beta` improves model loading and navigation through large catalogs, restores chat drafts when generation cannot start, and fixes attachment handling for first messages.

## Highlights

### Faster Model Loading and Selection

Model selection reuses the last catalog while fetching fresh availability and renders only the visible portion of long model lists.

- Cached catalogs are stored per user in the browser and refreshed from the server when the application loads. Provider connection changes also refresh the cached catalog.
- Large model menus keep search, keyboard navigation, pinning, and section jumps available without rendering every model row at once.
- The OpenRouter jump button leads directly to the metered model section, alongside connected subscription-provider sections.
- OpenRouter batch-only entries are excluded from model discovery, including its fallback catalog source.

### Reliable Chat Submission and Draft Recovery

Failed generation startup now leaves a visible error near the chat input and restores the submitted draft when no newer draft has been entered.

- Restore message text, attached files, and GitHub context after a failed submission without overwriting a newer draft.
- Block repeated sends while a submission is starting, streaming is active, or attachments are uploading.
- Prepare attachment content before creating chat nodes. Non-image attachments such as text documents use file content instead of failing client-side conversion, while image recognition covers additional extensions and image MIME types.
- Continue startup when the graph is already initialized, and bound the render wait when a hidden canvas does not report initialization.

## Self-Hosting and Upgrade Notes

Meridian `1.7.16-beta` introduces no database migrations, new configuration keys, new secrets, or dependency-file changes.

- Redeploy or restart the API and UI services to apply model filtering, catalog caching, selector, and chat fixes.
- Model catalogs now persist in browser local storage under per-user keys. Invalid cached catalogs are discarded and replaced through normal model discovery; no manual cache migration is required.
- Release publication now requires the release PR body to match its changelog exactly, including line endings and the trailing newline. Preserve the generated PR body when preparing a release.
