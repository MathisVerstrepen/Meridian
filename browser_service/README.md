# Browser Service

This private FastAPI sidecar owns Meridian's pinned Crawlee 1.8.2, Camoufox 0.5.4, Playwright 1.60.0, and Camoufox browser build `official/stable/152.0.4-beta.27`. The API keeps the existing `BrowserFetchManager.fetch(url) -> str`, typed errors, and shutdown call, but now makes one authenticated HTTP/1.1 request with no retry. Any direct or ordinary-proxy 403 admits that call; a direct or ordinary-proxy 401 admits it only with bounded generic `browser_challenge` evidence, while an ordinary authentication or permission 401 stops.

## Protocol and capacity

`GET /health` is unauthenticated and reveals only readiness, browser build, four active slots, and eight waiting slots. `POST /v1/fetch` requires the dedicated bearer token and accepts only a UUID request ID plus URL. Responses contain HTML or an allowlisted reason and optional 400–599 target status; raw exceptions, proxy values, response bodies, and request URLs are not returned or logged. Diagnostics contain sanitized URL/allowlisted headers and only the constant `browser_challenge` marker.

One Uvicorn worker owns one lazy crawler generation. Four one-page browser/controllers may be active and eight calls may wait FIFO. The 90-second total deadline starts before admission. Cancellation while waiting removes work before Crawlee submission; cancellation after admission retains its slot until crawler completion, preventing a fifth page. Cookies persist per slot without request affinity. Direct/proxy evidence is not sent in the request and does not authorize a wait. Navigation waits for `domcontentloaded`; the sidecar independently checks its own browser HTTP 401/403 response and enters hostname-independent challenge handling only with conservative body/header evidence. Handling keeps an exact 15-second budget, 5-second operation caps, and at most one reload. Access to challenged or blocked sites is not guaranteed.

## Security boundary and residuals

The image runs as `browseruser` with a read-only root, `/tmp` tmpfs, dedicated shared memory, all capabilities dropped, no-new-privileges, no init shim, and no in-container healthcheck. The Linux environment-holding Uvicorn process is PID 1. Before settings or children are created it sets both core limits to zero, sets and verifies `PR_SET_DUMPABLE=0`, then parses token/proxy and removes those names from live `os.environ`. Readiness and fetch admission recheck the invariant and fail closed. Camoufox receives only `HOME`, `PATH`, `LANG`, `LC_ALL`, and `TMPDIR`; the configured proxy still necessarily reaches Camoufox through its dedicated launch option.

The browser and sidecar parent share one container's PID, mount, and network namespaces. A compromised browser can signal or exhaust the sidecar and can reach/DoS the API over the required bidirectional `browser_control` network. This is not one-way or availability isolation. The separate API container prevents direct reads of API process environment/files, and the sidecar has no direct Compose membership/DNS attachment to database, Redis, or Neo4j networks. Browser egress can still reach routed, public, or host-published addresses; no new SSRF policy is claimed.

The build writes and startup verifies a complete cache path/size/SHA-256 manifest. These build-produced hashes detect stage-copy/runtime mutation but do not authenticate a compromised mutable upstream browser/add-on/GeoIP download. Full dependency hash locking and trusted immutable artifact pinning remain intentionally out of scope.

## Browser installation

The build-only `app.install_browser` adapter validates `app/camoufox_browser_version.txt` against the existing runtime version contract and selects the official fixed-version Linux asset for mapped `x86_64` or `arm64`. It uses Camoufox 0.5.4's `CamoufoxFetcher(selected_version=...)` installer rather than the CLI's release-list synchronization. No GitHub API release discovery, fallback browser repositories, build tokens, custom downloader, or dependency upgrades are required. Unsupported platforms fail before downloads.

Camoufox still creates version metadata, active configuration, its compatibility marker, and executable permissions. The adapter also populates GeoIP and default add-ons; the Docker build retains cache preflight, launch-data warming for Linux/macOS/Windows fingerprints, manifest generation, and removal of cache write permissions. Installation or GeoIP errors fail the build; preflight catches missing add-ons even when the library swallows their download errors. Runtime startup does not invoke the adapter.

The explicit official HTTPS asset URL avoids rate-limited release enumeration, not CDN failures or mutable upstream assets. No upstream checksum enforcement is claimed. `tests/offline_cache_probe.py` is a container-only probe: with networking disabled and a read-only root it verifies the cache, prepares all three fingerprint OS variants, launches a headless browser at `about:blank`, then verifies the manifest and non-writability again.

## Operation and rollback

Generate `LINK_EXTRACTION_BROWSER_SERVICE_TOKEN` with `python -c "import secrets; print(secrets.token_hex(32))"`; never reuse backend, JWT, or session secrets. It must contain at least 32 visible ASCII characters (`!` through `~`); whitespace, controls, and non-ASCII text fail closed. Rotate it by updating config and recreating API plus sidecar together. Local Compose publishes the configured port only on `127.0.0.1`; production uses service DNS and no host port. A valid proxy may perform one bounded public-IP lookup per browser generation through that proxy before using prefetched GeoIP data.

Restarting only `browser_service` clears active work, queue, cookies, and crawler state; callers receive typed failures and the API does not retry. Complete rollback is all-at-once: stop the new API/sidecar, restore the previous API image and previous Compose/config that supplied the browser proxy to API, restart, then remove the unused sidecar. There is no database or persisted crawler migration.

Local development requires Python 3.14. Run `make install-browser-service`, then `make test-browser-service`, `make lint-browser-service`, and `make typecheck-browser-service`. Older virtualenvs are rejected without modification; move them aside yourself or pass a fresh absolute `BROWSER_SERVICE_VENV` path to installation and checks. Runtime browser bytes are built into the `python:3.14-slim-bookworm` image, not installed into the API environment.
