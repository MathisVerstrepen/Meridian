# Meridian 1.7.12-beta

Meridian `1.7.12-beta` restores reliable Markdown rendering after the frontend runtime-safety migration by explicitly binding runtime helpers in both the Marked worker and its composable.

## Highlights

### Reliable Worker-Based Markdown Rendering

Markdown containing fenced code blocks or math can again use the dedicated worker with all runtime validation helpers available in the modules that call them.

- The Marked worker now imports its string validation and conversion helpers directly, preventing missing runtime bindings while processing worker requests and highlighted code output.
- The Marked composable now imports its string and undefined-value guards directly for worker initialization, worker responses, and main-thread Markdown results.
- A focused worker regression test renders a fenced TypeScript block and verifies that highlighted HTML is returned through the worker message boundary.

## Self-Hosting and Upgrade Notes

Meridian `1.7.12-beta` is a non-breaking frontend fix with no database migration, new configuration keys, new secrets, dependency-file changes, API changes, or data conversion steps.

- Rebuild and redeploy the UI to apply the Markdown worker fix; the API requires no release-specific configuration or migration work.
- Maintainers using the repository release automation must keep the release pull request body exactly equal to the merged changelog, including its trailing newline; CRLF and LF bodies are no longer treated as equivalent during publication validation.
