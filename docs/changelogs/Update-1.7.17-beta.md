# Meridian 1.7.17-beta

Meridian `1.7.17-beta` adds explicit choices for same-name attachment uploads and makes image playground references easier to inspect in a new tab.

## Highlights

### Choose How to Handle Duplicate Attachments

Chat and file-prompt attachments now ask what to do when an item with the same name already exists in the upload destination.

- Reuse the already uploaded file or upload the incoming file with a new name. Closing the dialog skips that file without uploading or attaching it.
- Compare labeled previews when both files are images. The dialog makes clear that matching names do not guarantee matching contents, and preview failures do not block your choice.
- Resolve collisions one at a time across batches, including pasted chat images. Files already attached are not added again when reused.
- Same-name folders cannot be attached; uploading with rename remains available. Collisions that arise during an upload also prompt for a choice rather than silently selecting a file.

### Inspect Image References in a New Tab

Reference thumbnails in the image playground composer now open the full image in a separate tab, matching the reference-opening behavior in image details.

- Open references from keyboard-focusable thumbnail links with visible focus styling.
- Continue dragging references to reorder them or removing individual references without opening a preview.

## Self-Hosting and Upgrade Notes

Meridian `1.7.17-beta` introduces no database migrations, new configuration keys, new secrets, or dependency-file changes. Existing stored files require no migration.

- Redeploy the frontend to apply the attachment dialogs and image-reference links. These features use existing backend file APIs.
- Release publication requires the release PR body to match its committed changelog exactly, including line endings and the trailing newline. Preserve the generated PR body when preparing the manual merge.
