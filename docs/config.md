# Meridian configuration

Meridian uses layered YAML for non-secret settings and a separate env file for secrets. The current release does not read or fall back to deployment TOML files. `docker/config/schema.yaml` is the authoritative inventory and translation to application environment variables.

## Table of contents

- [Setup and precedence](#setup-and-precedence)
- [How to read this reference](#how-to-read-this-reference)
- Configuration topics: [Deployment](#deployment) · [UI and API](#ui-and-api) · [Limits](#limits) · [OAuth](#oauth) · [Web search](#web-search) · [Browser and link extraction](#browser-and-link-extraction) · [Sandbox](#sandbox) · [Redis](#redis) · [PostgreSQL](#postgresql) · [Neo4j](#neo4j) · [GitHub integration](#github-integration) · [Sentry](#sentry) · [Email](#email) · [Secrets](#secrets)
- [Validation and generated files](#validation-and-generated-files)
- [Immediate migration from TOML](#immediate-migration-from-toml)

## Setup and precedence

From the repository root, run `make config-init-prod` for production/build or `make config-init-dev` for development. Each target creates only missing files, leaves existing files untouched, and sets the profile secrets file to mode `0600`. Edit the sparse override at `docker/config/overrides/{production|local}.yaml` and the matching required secrets file at `docker/config/secrets/{production|local}.env`, then preflight with `./docker/run.sh <prod|build|dev> --config-only`.

The renderer merges tracked `docker/config/defaults/common.yaml`, then the selected tracked profile (`production.yaml` for `prod`/`build`, `local.yaml` for `dev`), then the optional ignored sparse override. The mandatory ignored profile secrets file occupies a separate namespace. Every YAML layer must contain integer `version: 1` and a `settings` mapping. Keep overrides sparse, use lowercase YAML paths, and never place secrets or uppercase environment names in YAML.

## How to read this reference

Types are native YAML types; quoted numeric text is not an integer. Production defaults are the merged common and production layers. **Optional** means “may the administrator omit supplying this value?” It is `Yes` for every inherited YAML setting, `No` for required secrets, and `Yes` for optional secrets. After an edit, render again and recreate or restart every affected process named below; Compose reads generated values when creating services.

## Deployment

| YAML path or secret env key | Type | Production default | Optional |
|---|---|---|---|
| `deployment.environment` | string | `prod` | Yes |
| `deployment.name` | string | `meridian_prod` | Yes |
| `deployment.admin_user_creation` | string | `first` | Yes |
| `USERPASS` | string (secret) | empty | Yes |

### `deployment.environment`

Sets the application environment passed to the UI and API. The local profile uses `dev`; production/build use `prod`. Render and recreate the UI and API after changing it.

### `deployment.name`

Names the deployment and prefixes Compose container names; `docker/run.sh` also uses it in the local sandbox worker image name. The local profile uses `meridian`. Changing it effectively creates differently named containers, so render and recreate the deployment deliberately.

### `deployment.admin_user_creation`

Controls administrator assignment with accepted values `""`, `first`, `all_userpass`, and `all`. `first` makes the first configured bootstrap user an admin, `all_userpass` makes every bootstrap user an admin, `all` also makes every subsequently created account an admin, and `""` grants neither behavior. Unknown values stop API startup; restart the API after a change.

### `USERPASS`

Optional bootstrap credentials in comma-separated `username:password` pairs. An empty value creates no bootstrap users; malformed input stops API startup. Store it only in the profile secrets env file, restrict access to that file, and restart the API to create any users that do not already exist.

## UI and API

| YAML path or secret env key | Type | Production default | Optional |
|---|---|---|---|
| `ui.port` | integer | `3000` | Yes |
| `ui.api.public_base_url` | string | `http://localhost:8000` | Yes |
| `ui.api.internal_base_url` | string | `http://api:8000` | Yes |
| `api.port` | integer | `8000` | Yes |
| `api.logging.unbuffered` | integer | `1` | Yes |
| `api.cors.allowed_origins` | string | `http://localhost:3000` | Yes |
| `api.database.echo_queries` | boolean | `false` | Yes |

### `ui.port`

Sets the Nuxt Nitro listen port and host-published Compose port. No schema range is imposed; the value is passed through to Nuxt and Compose. Render and recreate the UI, and update network rules or reverse-proxy routing when changing it.

### `ui.api.public_base_url`

Sets the browser-visible API base URL. Use an API URL reachable from end-user browsers, not only from the Compose network. It is passed through as a string; render and recreate the UI after changing it.

### `ui.api.internal_base_url`

Sets the server-side Nuxt/Nitro API base URL. Production uses the Compose service URL; the local profile uses `http://localhost:8000`. Render and restart the UI after changing it, and ensure the UI process can resolve and reach the address.

### `api.port`

Sets the FastAPI listen port and the Compose host/container port. No schema range is imposed; it is passed through. Render and recreate the API, update the public/internal UI URLs as needed, and adjust network rules when changing it.

### `api.logging.unbuffered`

Sets Python's unbuffered-output flag; the default `1` keeps container logs immediate. The integer is passed through without a documented application-specific range. Render and restart the API after changing it.

### `api.cors.allowed_origins`

Sets the comma-separated browser origins accepted by API CORS handling. Use exact public UI origins and avoid broad origins in production. Render and restart the API after changing it.

### `api.database.echo_queries`

Enables SQLAlchemy query logging when `true`. It is useful for diagnosis but can be noisy and may expose query data in logs. Render and restart the API after changing it.

## Limits

| YAML path or secret env key | Type | Production default | Optional |
|---|---|---|---|
| `limits.free.web_search` | integer | `0` | Yes |
| `limits.free.link_extraction` | integer | `0` | Yes |
| `limits.free.storage_mib` | integer | `50` | Yes |
| `limits.premium.web_search` | integer | `200` | Yes |
| `limits.premium.link_extraction` | integer | `1000` | Yes |
| `limits.premium.storage_mib` | integer | `5120` | Yes |

All six limits must be non-negative integers, and zero is accepted. Query limits count operations in each user's existing account-anchored billing period. Storage values are binary MiB (`1 MiB = 1,048,576 bytes`) and are converted to bytes for enforcement and API responses. Lowering a query limit does not reset usage, and lowering storage does not delete files; later operations follow existing quota boundaries. Every limit change requires an API restart.

### `limits.free.web_search`

Sets the number of metered web-search operations available to a free user per existing billing period. The default `0` allows none.

### `limits.free.link_extraction`

Sets the number of metered link-extraction operations available to a free user per existing billing period. The default `0` allows none.

### `limits.free.storage_mib`

Sets the free-plan storage quota in MiB. The default `50` becomes `52,428,800` bytes for enforcement.

### `limits.premium.web_search`

Sets the number of metered web-search operations available to a premium user per existing billing period.

### `limits.premium.link_extraction`

Sets the number of metered link-extraction operations available to a premium user per existing billing period.

### `limits.premium.storage_mib`

Sets the premium-plan storage quota in MiB. The default `5120` is 5 GiB and becomes `5,368,709,120` bytes for enforcement.

## OAuth

| YAML path or secret env key | Type | Production default | Optional |
|---|---|---|---|
| `ui.oauth.disabled` | string | `true` | Yes |
| `ui.oauth.github.client_id` | string | empty | Yes |
| `ui.oauth.google.client_id` | string | empty | Yes |
| `NUXT_OAUTH_GITHUB_CLIENT_SECRET` | string (secret) | empty | Yes |
| `NUXT_OAUTH_GOOGLE_CLIENT_SECRET` | string (secret) | empty | Yes |

These keys configure login OAuth, not the GitHub repository integration documented later. Configure a provider's client ID and secret as a pair and recreate the UI; the API also consumes the GitHub pair and Google client ID, so restart it too. The backend can fall back from the GitHub login pair to the separate integration pair, but keeping the contracts separate avoids coupling login to repository access.

### `ui.oauth.disabled`

Controls whether OAuth login is hidden. This is intentionally a YAML string, and only the exact rendered text `true` disables OAuth in Nuxt. Recreate the UI after changing it.

### `ui.oauth.github.client_id`

Sets the public GitHub OAuth client ID for login. Empty leaves that login provider unconfigured. The value is passed to the UI and API; recreate both after changing it.

### `ui.oauth.google.client_id`

Sets the public Google OAuth client ID used by the UI flow and accepted by backend ID-token validation. It may contain comma-separated IDs at the backend boundary, but the normal deployment uses one provider ID. Recreate the UI and API after changing it.

### `NUXT_OAUTH_GITHUB_CLIENT_SECRET`

Sets the GitHub OAuth secret paired with the login client ID. Keep it only in the profile secrets env file, never in YAML or browser-public configuration. Recreate the UI and API after rotation.

### `NUXT_OAUTH_GOOGLE_CLIENT_SECRET`

Sets the Google OAuth secret paired with the login client ID. Keep it only in the profile secrets env file and recreate the UI after rotation.

## Web search

| YAML path or secret env key | Type | Production default | Optional |
|---|---|---|---|
| `search.searxng.url` | string | `http://localhost:8888` | Yes |
| `search.google.cse_id` | string | `13b59231658654d8a` | Yes |
| `GOOGLE_SEARCH_API_KEY` | string (secret) | empty | Yes |

Meridian tries SearXNG first for normal metered searches and falls back to Google Custom Search when SearXNG fails or returns no usable results. Restart the API after changing any provider setting.

### `search.searxng.url`

Sets the SearXNG service base URL used by the API. It is passed through without schema URL validation, so verify reachability from the API process.

### `search.google.cse_id`

Sets the Google Custom Search Engine identifier. It is useful only with a working Google API key; keep the identifier in YAML and the credential in the secrets file.

### `GOOGLE_SEARCH_API_KEY`

Sets the optional Google Custom Search credential used by the fallback provider unless a user explicitly supplies a custom key. Keep it only in the profile secrets env file; an empty value leaves the fallback without an administrator key.

## Browser and link extraction

| YAML path or secret env key | Type | Production default | Optional |
|---|---|---|---|
| `browser.port` | integer | `5010` | Yes |
| `browser.service_url` | string | `http://browser_service:5010` | Yes |
| `LINK_EXTRACTION_BROWSER_SERVICE_TOKEN` | string (secret) | None — administrator supplied | No |
| `LINK_EXTRACTION_BROWSER_PROXY_URL` | string (secret) | empty | Yes |

The browser sidecar is a fallback after direct/ordinary-proxy extraction paths; sidecar readiness does not gate those earlier paths. Local Compose publishes the sidecar only on `127.0.0.1`, while production exposes it only inside Compose networking.

### `browser.port`

Sets the sidecar listen port. The browser service validates the range `1`–`65535`; both Compose files also use it to construct the API container's sidecar URL. Render and recreate the API and browser sidecar together after changing it.

### `browser.service_url`

Sets the URL consumed by a host-run API; the local profile uses `http://localhost:5010`. The API requires HTTP(S), a hostname, and no credentials, query, or fragment. Both Compose files instead construct the API container URL from `browser.port`, so overriding this production YAML path does not rewire that Compose assignment. Restart a host API after changing it.

### `LINK_EXTRACTION_BROWSER_SERVICE_TOKEN`

Authenticates API-to-sidecar requests. Use a dedicated value with at least 32 visible ASCII characters; whitespace, non-ASCII text, control characters, and known placeholder words are rejected. Store it only in the profile secrets env file and rotate it by recreating the API and browser sidecar together.

### `LINK_EXTRACTION_BROWSER_PROXY_URL`

Optionally routes only the browser sidecar through an HTTP(S) proxy; empty means direct browser egress. A proxy URL may include percent-encoded credentials, but username and password must appear together; invalid input safely falls back to direct egress. Treat every non-empty URL as sensitive, verify legal authorization, and recreate the browser sidecar after changing it. The local host env output intentionally omits this key so proxy credentials remain sidecar-only.

## Sandbox

| YAML path or secret env key | Type | Production default | Optional |
|---|---|---|---|
| `sandbox.manager.port` | integer | `5000` | Yes |
| `sandbox.manager.url` | string | `http://sandbox_manager:5000` | Yes |
| `sandbox.capacity.max_concurrent` | integer | `10` | Yes |
| `sandbox.queue.wait_seconds` | integer | `5` | Yes |
| `sandbox.execution.timeout_seconds` | integer | `10` | Yes |
| `sandbox.execution.output_limit_bytes` | integer | `51200` | Yes |
| `sandbox.execution.code_max_bytes` | integer | `102400` | Yes |
| `sandbox.artifacts.max_files` | integer | `20` | Yes |
| `sandbox.artifacts.max_file_bytes` | integer | `5242880` | Yes |
| `sandbox.artifacts.max_total_bytes` | integer | `10485760` | Yes |
| `sandbox.inputs.max_files` | integer | `20` | Yes |
| `sandbox.inputs.max_file_bytes` | integer | `5242880` | Yes |
| `sandbox.inputs.max_total_bytes` | integer | `10485760` | Yes |
| `sandbox.resources.memory_limit` | string | `256m` | Yes |
| `sandbox.resources.cpu_nano_cpus` | integer | `500000000` | Yes |
| `sandbox.resources.pids_limit` | integer | `64` | Yes |
| `sandbox.resources.tmpfs_size` | string | `50m` | Yes |
| `sandbox.runtime` | string | `nsjail` | Yes |

These values are loaded when the sandbox manager starts and applied to worker containers it creates. Except where stated, the schema enforces native type but no numeric minimum; use positive, capacity-appropriate values. Render and recreate the sandbox manager after any sandbox change; restart the API as well when changing its manager URL.

### `sandbox.manager.port`

Sets the sandbox manager listen and Compose exposure port. Keep it aligned with the manager URL and network rules.

### `sandbox.manager.url`

Sets the API-to-manager URL. Production uses the Compose service URL; the local profile uses `http://localhost:5000`. Verify reachability from the API process.

### `sandbox.capacity.max_concurrent`

Caps concurrently running sandbox workers. Higher values increase Docker host CPU, memory, and process demand.

### `sandbox.queue.wait_seconds`

Sets how many seconds a request may wait for capacity. The manager consumes it as a duration; a short value rejects sooner under saturation.

### `sandbox.execution.timeout_seconds`

Sets the maximum worker execution duration in seconds. It bounds executed code rather than queue waiting.

### `sandbox.execution.output_limit_bytes`

Caps captured stdout/stderr in bytes. The default is 50 KiB; output beyond the enforced boundary is not available to callers.

### `sandbox.execution.code_max_bytes`

Caps submitted source-code size in bytes. The default is 100 KiB.

### `sandbox.artifacts.max_files`

Caps the number of artifact files returned by one execution.

### `sandbox.artifacts.max_file_bytes`

Caps one returned artifact file in bytes. The default is 5 MiB.

### `sandbox.artifacts.max_total_bytes`

Caps the combined returned artifact size in bytes. The default is 10 MiB and should not be lower than intended per-file workloads.

### `sandbox.inputs.max_files`

Caps the number of files supplied to one sandbox execution.

### `sandbox.inputs.max_file_bytes`

Caps one sandbox input file in bytes. The default is 5 MiB.

### `sandbox.inputs.max_total_bytes`

Caps the combined sandbox input size in bytes. The default is 10 MiB.

### `sandbox.resources.memory_limit`

Sets the Docker memory limit for each worker using Docker size syntax. Size it together with concurrency and host memory.

### `sandbox.resources.cpu_nano_cpus`

Sets each worker's Docker CPU quota in nano-CPUs; `500000000` is 0.5 CPU. Multiply by maximum concurrency when planning host capacity.

### `sandbox.resources.pids_limit`

Caps processes in each worker container. Values that are too low can prevent legitimate runtimes from starting child processes.

### `sandbox.resources.tmpfs_size`

Sets the worker tmpfs size using Docker size syntax. This consumes host memory and should be planned with worker concurrency.

### `sandbox.runtime`

Selects the execution runtime. The current executor supports only `nsjail`; other strings pass schema validation but fail execution, so do not change this without matching runtime support.

## Redis

| YAML path or secret env key | Type | Production default | Optional |
|---|---|---|---|
| `redis.host` | string | `redis` | Yes |
| `redis.port` | integer | `6379` | Yes |
| `REDIS_PASSWORD` | string (secret) | None — administrator supplied | No |

### `redis.host`

Sets the Redis hostname used by the API. The local profile uses `localhost`; production uses the Compose service name. Render and restart the API after changing it.

### `redis.port`

Sets the API Redis port and the host-published port, while the Compose Redis container continues listening internally on `6379`. Keep the default for API-to-Redis traffic inside Compose unless the topology is changed consistently. Render and recreate Redis and restart the API after changing it.

### `REDIS_PASSWORD`

Authenticates both the Redis server and API client. Store it only in the profile secrets env file. Rotate by recreating Redis and the API together; existing Redis data remains in its volume.

## PostgreSQL

| YAML path or secret env key | Type | Production default | Optional |
|---|---|---|---|
| `postgres.database` | string | `postgres` | Yes |
| `postgres.username` | string | `postgres` | Yes |
| `postgres.host` | string | `db` | Yes |
| `postgres.port` | integer | `5432` | Yes |
| `postgres.pool.size` | integer | `10` | Yes |
| `postgres.pool.max_overflow` | integer | `20` | Yes |
| `postgres.tuning.shared_buffers` | string | `4GB` | Yes |
| `postgres.tuning.effective_cache_size` | string | `12GB` | Yes |
| `postgres.tuning.work_mem` | string | `32MB` | Yes |
| `postgres.tuning.maintenance_work_mem` | string | `1GB` | Yes |
| `postgres.tuning.random_page_cost` | number | `1.1` | Yes |
| `postgres.tuning.max_worker_processes` | integer | `8` | Yes |
| `postgres.tuning.max_parallel_workers_per_gather` | integer | `4` | Yes |
| `postgres.tuning.max_parallel_workers` | integer | `8` | Yes |
| `postgres.logging.min_duration_statement` | string | `250ms` | Yes |
| `postgres.logging.lock_waits` | string | `on` | Yes |
| `POSTGRES_PASSWORD` | string (secret) | None — administrator supplied | No |

Database tuning values are passed as PostgreSQL server parameters; PostgreSQL validates their accepted syntax and ranges. Render and recreate PostgreSQL after changing server, identity, port, tuning, or logging values. Restart the API after connection or pool changes, and run migrations with the same rendered profile connection settings.

### `postgres.database`

Sets the database created/selected by the PostgreSQL container and used by the API. Changing it against an existing volume does not migrate data or rename the existing database.

### `postgres.username`

Sets the PostgreSQL bootstrap and API username. Changing it against an initialized volume does not automatically recreate roles.

### `postgres.host`

Sets the database host used by the API and local migrations. Production uses `db`; the local profile uses `localhost`.

### `postgres.port`

Sets the PostgreSQL server port, host publication, health check, and API connection port. Keep all external clients and firewall rules aligned.

### `postgres.pool.size`

Sets the SQLAlchemy async pool's persistent connection count per API process. Size it against PostgreSQL's total connection capacity.

### `postgres.pool.max_overflow`

Sets additional temporary SQLAlchemy connections allowed above the base pool size. Total peak API connections per process can reach base plus overflow.

### `postgres.tuning.shared_buffers`

Sets PostgreSQL shared memory for cached database pages. The default `4GB` assumes sufficient container/host memory; reduce it on smaller hosts.

### `postgres.tuning.effective_cache_size`

Sets the planner's estimate of memory available for caching; it is not a direct allocation. Tune it to the database host's realistic cache capacity.

### `postgres.tuning.work_mem`

Sets memory available per PostgreSQL sort/hash operation, not per server. Concurrent complex queries can consume this value multiple times.

### `postgres.tuning.maintenance_work_mem`

Sets memory for maintenance work such as vacuuming and index creation. Ensure the host can sustain it alongside normal workload memory.

### `postgres.tuning.random_page_cost`

Sets the planner cost for non-sequential page reads. Lower values favor index access; tune from measured storage behavior rather than treating it as a duration.

### `postgres.tuning.max_worker_processes`

Caps PostgreSQL background worker processes and constrains parallel-worker capacity. Keep it at least as large as the intended total parallel-worker setting.

### `postgres.tuning.max_parallel_workers_per_gather`

Caps workers used by one parallel query gather operation. High values can let one query consume much of the worker pool.

### `postgres.tuning.max_parallel_workers`

Caps total PostgreSQL parallel workers. Size it with `max_worker_processes` and available CPU.

### `postgres.logging.min_duration_statement`

Sets PostgreSQL's slow-statement logging threshold using PostgreSQL duration syntax. The default logs statements taking at least 250 ms; lower thresholds increase log volume and may expose query text.

### `postgres.logging.lock_waits`

Sets PostgreSQL lock-wait logging using PostgreSQL's string boolean syntax. The default `on` records waits that exceed the server's deadlock-timeout behavior.

### `POSTGRES_PASSWORD`

Authenticates the PostgreSQL container, health checks, migrations, and API. Store it only in the profile secrets env file. Rotation must update/recreate PostgreSQL and restart every database client; an initialized volume may require changing the database role password explicitly.

## Neo4j

| YAML path or secret env key | Type | Production default | Optional |
|---|---|---|---|
| `neo4j.username` | string | `neo4j` | Yes |
| `neo4j.host` | string | `neo4j` | Yes |
| `neo4j.bolt.port` | integer | `7687` | Yes |
| `neo4j.bolt.address` | string | `0.0.0.0:7687` | Yes |
| `neo4j.http.port` | integer | `7474` | Yes |
| `neo4j.http.address` | string | `0.0.0.0:7474` | Yes |
| `NEO4J_PASSWORD` | string (secret) | None — administrator supplied | No |

### `neo4j.username`

Sets the API and health-check username. Compose creates authentication as the built-in `neo4j` user, so keep this value `neo4j` unless the container authentication setup is changed consistently. Restart the API and recreate Neo4j after changing it.

### `neo4j.host`

Sets the Bolt host used by the API. Production uses the Compose service name; the local profile uses `localhost`. Restart the API after changing it.

### `neo4j.bolt.port`

Sets the API/health-check Bolt port and host-published port. Keep it synchronized with the port in the Bolt listen address; recreate Neo4j and restart the API after changing it.

### `neo4j.bolt.address`

Sets Neo4j's internal Bolt listen address. It is passed directly to Neo4j; keep its port aligned with `neo4j.bolt.port` and avoid restricting the bind address in a way that breaks container networking.

### `neo4j.http.port`

Sets the host-published Neo4j HTTP/browser port. Keep it synchronized with the HTTP listen address and recreate Neo4j after changing it.

### `neo4j.http.address`

Sets Neo4j's internal HTTP listen address. It is passed directly to Neo4j; keep its port aligned with `neo4j.http.port`.

### `NEO4J_PASSWORD`

Authenticates Neo4j, its health check, and the API. Store it only in the profile secrets env file. Rotate it across Neo4j and the API together; an initialized volume may require an explicit database password change.

## GitHub integration

| YAML path or secret env key | Type | Production default | Optional |
|---|---|---|---|
| `integrations.github.client_id` | string | empty | Yes |
| `integrations.github.redirect_uri` | string | `http://localhost:3000/settings?tab=github` | Yes |
| `GITHUB_CLIENT_SECRET` | string (secret) | empty | Yes |

These settings configure GitHub account/repository integration from application settings, separately from login OAuth. Configure the client ID and secret as a pair, register the exact redirect URI with GitHub, and restart the API after changes.

### `integrations.github.client_id`

Sets the GitHub OAuth application client ID for repository integration. Empty leaves the integration unconfigured; this identifier is non-secret and belongs in YAML.

### `integrations.github.redirect_uri`

Sets the callback URI for repository integration. Replace the localhost production default with the externally reachable UI settings URL and keep it exactly synchronized with the GitHub OAuth application registration.

### `GITHUB_CLIENT_SECRET`

Sets the secret paired with the repository-integration client ID. Keep it only in the profile secrets env file. The backend may use this pair as a fallback for GitHub login when the dedicated login pair is absent, so rotation can affect both flows.

## Sentry

| YAML path or secret env key | Type | Production default | Optional |
|---|---|---|---|
| `observability.sentry.dsn` | string | empty | Yes |

### `observability.sentry.dsn`

Sets the Sentry DSN for API monitoring and Compose-derived frontend public configuration; empty disables initialization. It remains non-secret YAML because the frontend receives it publicly. Render and recreate both API and UI after changing it, and remember that application events may leave the deployment for the configured Sentry service.

## Email

| YAML path or secret env key | Type | Production default | Optional |
|---|---|---|---|
| `email.smtp.server` | string | `smtp.example.com` | Yes |
| `email.smtp.port` | integer | `587` | Yes |
| `email.smtp.username` | string | empty | Yes |
| `email.smtp.auth_protocol` | string | `TLS` | Yes |
| `email.smtp.from_email` | string | empty | Yes |
| `SMTP_PASSWORD` | string (secret) | empty | Yes |

Email delivery currently requires server, port, username, and password to all be non-empty. If any is missing, the API logs a configuration error and does not send the verification message. Restart the API after changing any email value.

### `email.smtp.server`

Sets the SMTP hostname. Replace the example production default with the mail provider's server and ensure the API can resolve and reach it.

### `email.smtp.port`

Sets the SMTP port. The integer is passed to the SMTP client; choose the port corresponding to the configured connection mode and provider.

### `email.smtp.username`

Sets the required SMTP login username. It is non-secret YAML, but avoid embedding credentials or tokens in this field.

### `email.smtp.auth_protocol`

Selects connection behavior: `SSL` uses implicit TLS, `STARTTLS` explicitly upgrades a plain connection, and every other value—including the production default `TLS`—uses the non-implicit, non-STARTTLS branch before login. Match the provider exactly; no schema enum restricts this string.

### `email.smtp.from_email`

Sets the message sender address. The current prerequisite check does not require it to be non-empty, but successful delivery may depend on a valid provider-authorized address.

### `SMTP_PASSWORD`

Sets the required SMTP login password. Keep it only in the profile secrets env file; empty disables delivery through the prerequisite check. Restart the API after rotation.

## Secrets

| YAML path or secret env key | Type | Production default | Optional |
|---|---|---|---|
| `NUXT_SESSION_PASSWORD` | string (secret) | None — administrator supplied | No |
| `MASTER_OPEN_ROUTER_API_KEY` | string (secret) | None — administrator supplied | No |
| `BACKEND_SECRET` | string (secret) | None — administrator supplied | No |
| `JWT_SECRET_KEY` | string (secret) | None — administrator supplied | No |

Keep every key below only in `docker/config/secrets/{production|local}.env`, restrict access to that file, and use independently generated high-entropy values. Never copy generated env outputs into source control or expose them in logs, diffs, issues, or support output.

### `NUXT_SESSION_PASSWORD`

Encrypts Nuxt session cookies. Recreate the UI after rotation; existing cookies encrypted under the previous key can no longer be decrypted, so users may need to establish new sessions.

### `MASTER_OPEN_ROUTER_API_KEY`

Is required for API startup and model-catalog access. User generation requests use each user's separately stored provider key. Restart the API after rotation.

### `BACKEND_SECRET`

Protects persisted provider/API keys with authenticated encryption. Restart the API after changing it, and do not rotate casually: data encrypted under the old key becomes undecryptable without a planned re-encryption or recovery strategy.

### `JWT_SECRET_KEY`

Signs and validates API access tokens. Restart the API after rotation; existing access tokens signed with the prior key stop validating.

## Validation and generated files

Run `./docker/run.sh <dev|prod|build> --config-only` from the repository root (or `./run.sh ...` from `docker/`). Preflight validates and renders without pulling, building, starting, or health-checking Docker services. `down` and `down -v` remain available before validation, so bad new input cannot block shutdown.

Validation rejects unsupported versions, unknown top-level keys, unknown paths, empty mappings, env-shaped YAML paths, secrets in YAML, duplicate/null/sequence/multiline values, native type mismatches, missing effective settings, negative plan limits, malformed/unknown/duplicate secret lines, and missing or empty required secrets. Secret files are parsed as data without `source`, `eval`, or shell expansion. Failures identify the relevant path/key without printing its value and leave prior generated outputs untouched.

Successful rendering is deterministic and atomically replaces these mode-`0600` outputs:

- Production/build: `docker/env/.env.prod`.
- Local Compose: `docker/env/.env.compose.local`.
- Local host API, migrations, and frontend generation: `docker/env/.env.local`.

The local host output omits only the browser proxy secret; local Compose retains it for the sidecar. `docker/run.sh` subsequently adds `SANDBOX_WORKER_IMAGE`, and production semantic-version arguments supply `IMAGE_TAG`. The following external/generated variables are not administrator-facing schema entries: `NUXT_PUBLIC_VERSION`, `GOOGLE_CLIENT_ID`, `REDIS_ANNOTATIONS_TTL_SECONDS`, `REDIS_PENDING_TOOL_CONTINUATION_TTL_SECONDS`, `MERMAID_VALIDATOR_SCRIPT`, `IMAGE_TAG`, and `SANDBOX_WORKER_IMAGE`.

## Immediate migration from TOML

1. Before updating, privately back up the old ignored deployment configuration outside the repository and inventory its values without printing secrets.
2. Run `make config-init-prod` or `make config-init-dev`. Edit only the matching sparse YAML override and profile secrets env file.
3. Translate old non-secret env names to the friendly YAML paths above, adding only values that differ from inherited defaults. Transfer secret keys only to the secrets env file; never put uppercase non-secret names or secrets in YAML.
4. Run the intended `./docker/run.sh <prod|build|dev> --config-only` preflight, including an intended production version argument when applicable, and resolve every error before service changes.
5. Start with the normal command and flags. The current release ignores old deployment TOML files; retain the private backup only through the rollback window and keep future overrides sparse so tracked defaults can evolve.
