# Meridian 1.7.15-beta

Meridian `1.7.15-beta` improves how follow-up conversations retain tool results, keeps legacy tool-context markup out of chat, and upgrades Python services and sandbox execution to Python 3.14. This release also separates pull-request image checks from publishing and updates shared build caching.

## Highlights

### Tool Results in Follow-Up Conversations

Completed tool calls can now return to model history as paired calls and results rather than being embedded in assistant prose.

- Replay uses referenced, persisted tool arguments and model-facing results from the same user, graph, generator, and parallel-model entry. Missing, pending, mismatched, or malformed records are omitted without rerunning tools.
- Supported provider integrations receive native historical tool pairs. Claude Agent and GitHub Copilot receive explicitly labeled historical tool data in their prompt transcripts, rather than reconstructed native sessions.
- Context mergers retain complete generator turns when selecting recent history, including eligible tool context. Parallel aggregators receive child answers as user context rather than system instructions.
- Historical image inspection keeps its existing bounded provenance without loading old image pixels. Replaying history does not enable tools disabled for the current request.

### Cleaner Chat History

Reserved legacy tool-context blocks stay out of rendered replies and derived conversation text.

- Hide complete and unfinished legacy tool-context blocks, including partial opening markers while responses stream.
- Preserve surrounding prose, ordinary JSON, and escaped examples without rewriting saved replies, tool records, or cached summaries.
- Keep displayed chat history focused on messages and summary cards rather than synthetic tool-call messages.

### Updated Runtime and Image Builds

Python services and sandbox workers now use Python 3.14, with build checks aligned to that runtime.

- Browser-service builds select the pinned official Camoufox asset directly instead of querying release listings, avoiding release-discovery rate limits while retaining browser-cache validation.
- Pull-request image checks build without publishing images or caches. Guarded tag publications update shared registry build caches for later builds.
- Image matrices allow up to five concurrent builds after lint passes, subject to runner availability. Missing cache imports fall back to cold builds.

## Self-Hosting and Upgrade Notes

Meridian `1.7.15-beta` requires Python 3.14 for source-based Python environments and changes the Python runtime used by sandbox code. It adds no database schema migration, configuration keys, or secrets.

- Redeploy matching API and UI versions, and update the browser-service, sandbox-manager, and sandbox Python worker images to apply the runtime and history changes. Check custom sandbox code and packages for Python 3.14 compatibility.
- Recreate older development virtual environments with Python 3.14, or supply fresh environment paths. Install and check scripts reject older environments without replacing them automatically.
- Development dependencies update mypy to `1.19.1` across Python services and add pytest `9.0.3` to the API development environment. Application dependency manifests and frontend lockfiles are unchanged.
- Existing chats and tool records require no data conversion. Historical replay uses eligible stored model-facing payloads; it does not reconstruct missing tool facts or original provider reasoning.
- Existing database migration files receive import corrections only; no new migration revision is introduced.
- Shared registry build caches are publicly readable intermediate build layers, not release artifacts. Keep credentials and private data out of build inputs and intermediate layers. Pull-request checks do not write these caches.
