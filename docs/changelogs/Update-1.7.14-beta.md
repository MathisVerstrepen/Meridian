# Meridian 1.7.14-beta

Meridian `1.7.14-beta` adds expandable Markdown tables with spreadsheet-friendly copy options, direct navigation to user messages, and OpenAI Codex catalog support for integer-version model names such as GPT-6 Astra. Chat now preserves your scroll position when a streamed response finishes.

## Highlights

### Expandable Markdown Tables

Wide tables are easier to read in chat and inspect in an expanded view.

- Tables keep short columns compact, wrap long cell content, and scroll horizontally within the response rather than stretching the chat layout.
- Open an expanded table with a sticky header and first column to keep labels visible while scrolling through large results.
- Copy the expanded table as Markdown, TSV, or CSV. Spreadsheet exports preserve signed numbers while treating formula-like text as text.
- Expanded tables show a snapshot of the rendered content when opened, with keyboard-accessible scrolling and close controls.

### Direct Chat Navigation

A compact user-message navigator replaces the separate user and assistant arrow controls.

- Hover or focus a navigation marker to preview its user message, then select it to jump directly to that message near the top of the chat.
- Navigation previews omit internal node markers and condense long messages into short text previews.
- Reading earlier messages no longer snaps the chat back to the bottom when streaming finishes. Following the bottom or explicitly returning to it continues to follow the response.
- Fixed an error when a chat message renderer is removed and its editing reference is cleared.

### OpenAI Codex Model Discovery

OpenAI Codex model discovery now recognizes eligible GPT model names with integer major versions.

- Catalog entries such as `gpt-6` and `gpt-6-astra` can appear when supplied by the model catalog.
- Multi-digit minor versions such as `gpt-5.10` are compared numerically, while the existing GPT minimum-version and nano exclusions remain in place.

## Self-Hosting and Upgrade Notes

Meridian `1.7.14-beta` introduces no database migration, new configuration keys, or new secrets. Existing stored data requires no migration.

- Redeploy the API and UI to apply the Codex catalog and chat changes. The bundled OpenAI Codex runtime is updated from `0.139.0` to `0.154.0`; source installations must refresh the API runtime dependencies as part of the upgrade.
- The old role-based message navigation arrows and their Ctrl/Cmd or Alt arrow-key shortcuts are removed in favor of the user-message navigator.
- Release publication now requires the release PR body to match the changelog exactly, including line endings and the trailing newline. Do not reformat the generated PR body before merging.
