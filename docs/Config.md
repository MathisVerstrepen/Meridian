# Meridian Configuration File

Meridian uses TOML configuration files under `docker/`:

- `config.local.toml` is used for local development by `docker/run.sh dev`.
- `config.toml` is used for production/self-hosted deployments by `docker/run.sh prod`.
- `docker/run.sh` converts the selected TOML file into a Docker Compose env file.

The sections below match the current `docker/config.example.toml` and `docker/config.local.example.toml` fields.

## `[general]`

| Field | Type | Default / example | Description |
| --- | --- | --- | --- |
| `ENV` | String | `dev`, `prod` | Application environment. `dev` enables local development environment loading in the backend. |
| `NAME` | String | `meridian`, `meridian_prod` | Logical deployment name used as the Docker container name prefix. |
| `USERPASS` | String | `admin:adminpwd,user1:user1pwd` | Comma-separated `username:password` pairs used to create initial `userpass` accounts on API startup. Leave empty to create no bootstrap users. |
| `ADMIN_USER_CREATION` | String | `first` | Controls admin assignment for newly created accounts. Valid values: `""` creates no admins, `first` makes the first configured `USERPASS` user an admin, `all_userpass` makes all configured startup `USERPASS` users admins, and `all` makes every newly created account an admin. If unset, Docker Compose and the backend default to `first`. |

## `[ui]`

| Field | Type | Default / example | Description |
| --- | --- | --- | --- |
| `NITRO_PORT` | Integer | `3000` | Port used by the Nuxt Nitro server and exposed by Docker Compose. |
| `NUXT_PUBLIC_API_BASE_URL` | String | `http://localhost:8000` | Public browser-facing base URL for the API. Use the externally reachable API URL. |
| `NUXT_API_INTERNAL_BASE_URL` | String | `http://api:8000` or `http://localhost:8000` | Internal server-side base URL used by Nuxt/Nitro when proxying API requests. Use the Docker service URL in Compose deployments and localhost for local development. |
| `NUXT_SESSION_PASSWORD` | String | 64+ chars | Secret used to encrypt Nuxt session cookies. Generate with `python -c "import os; print(os.urandom(32).hex())"`. Treat as secret. |
| `NUXT_PUBLIC_IS_OAUTH_DISABLED` | String boolean | `"true"`, `"false"` | Disables OAuth login buttons in the UI when exactly set to `"true"`. |
| `NUXT_OAUTH_GITHUB_CLIENT_ID` | String | `""` | GitHub OAuth client ID used by the Nuxt auth flow. |
| `NUXT_OAUTH_GITHUB_CLIENT_SECRET` | String | `""` | GitHub OAuth client secret used by the Nuxt auth flow. Treat as secret. |
| `NUXT_OAUTH_GOOGLE_CLIENT_ID` | String | `""` | Google OAuth client ID used by the Nuxt auth flow and accepted by the backend for Google ID token validation. |
| `NUXT_OAUTH_GOOGLE_CLIENT_SECRET` | String | `""` | Google OAuth client secret used by the Nuxt auth flow. Treat as secret. |

## `[api]`

| Field | Type | Default / example | Description |
| --- | --- | --- | --- |
| `API_PORT` | Integer | `8000` | Port used by the FastAPI server and exposed by Docker Compose. |
| `PYTHONUNBUFFERED` | Integer | `1` | Forces Python stdout/stderr to be unbuffered. Recommended for container logs. |
| `ALLOW_CORS_ORIGINS` | String | `http://localhost:3000` | Comma-separated list of allowed browser origins. Use the public UI origin in production. |
| `MASTER_OPEN_ROUTER_API_KEY` | String | `""` | OpenRouter API key required for API startup and model catalog access. Treat as secret. |
| `DATABASE_ECHO` | Boolean | `false` | Enables SQLAlchemy SQL logging when true. Useful for debugging, noisy in production. |
| `BACKEND_SECRET` | String | 64 hex chars | Backend application secret for cryptographic operations. Generate with `python -c "import os; print(os.urandom(32).hex())"`. Treat as secret. |
| `JWT_SECRET_KEY` | String | 64 hex chars | Secret used to sign JWT access tokens. Generate with `python -c "import os; print(os.urandom(32).hex())"`. Treat as secret. |
| `SEARXNG_URL` | String | `http://localhost:8888` | Base URL for the SearXNG search service used by search tools. |
| `GOOGLE_SEARCH_API_KEY` | String | `""` | Google Custom Search API key used as a search provider/fallback. Treat as secret. |
| `GOOGLE_CSE_ID` | String | `""` | Google Custom Search Engine ID paired with `GOOGLE_SEARCH_API_KEY`. |

## `[sandbox]`

These settings configure the sandbox manager service and code-execution worker containers.

| Field | Type | Default / example | Description |
| --- | --- | --- | --- |
| `SANDBOX_MANAGER_PORT` | Integer | `5000` | Port used by the sandbox manager service. |
| `SANDBOX_MANAGER_URL` | String | `http://sandbox_manager:5000` or `http://localhost:5000` | URL the API uses to call the sandbox manager. Use the Compose service URL in Docker deployments and localhost for local development. |
| `MAX_CONCURRENT_SANDBOXES` | Integer | `10` | Maximum number of sandboxes the manager may run concurrently. |
| `SANDBOX_QUEUE_WAIT_SECONDS` | Integer | `5` | Queue wait timeout when sandbox capacity is exhausted. |
| `EXECUTION_TIMEOUT_SECONDS` | Integer | `10` | Maximum runtime for a sandboxed execution. |
| `SANDBOX_OUTPUT_LIMIT_BYTES` | Integer | `51200` | Maximum captured stdout/stderr output size. |
| `SANDBOX_CODE_MAX_BYTES` | Integer | `102400` | Maximum submitted code size. |
| `SANDBOX_ARTIFACT_MAX_FILES` | Integer | `20` | Maximum number of artifact files a sandbox execution may return. |
| `SANDBOX_ARTIFACT_MAX_FILE_BYTES` | Integer | `5242880` | Maximum size of a single returned artifact file. |
| `SANDBOX_ARTIFACT_MAX_TOTAL_BYTES` | Integer | `10485760` | Maximum total size of returned artifact files. |
| `SANDBOX_INPUT_MAX_FILES` | Integer | `20` | Maximum number of input files supplied to a sandbox execution. |
| `SANDBOX_INPUT_MAX_FILE_BYTES` | Integer | `5242880` | Maximum size of a single input file. |
| `SANDBOX_INPUT_MAX_TOTAL_BYTES` | Integer | `10485760` | Maximum total size of input files. |
| `SANDBOX_MEMORY_LIMIT` | String | `256m` | Docker memory limit for each sandbox worker container. |
| `SANDBOX_CPU_NANO_CPUS` | Integer | `500000000` | Docker CPU limit in nano CPUs. `500000000` is 0.5 CPU. |
| `SANDBOX_PIDS_LIMIT` | Integer | `64` | Process count limit for each sandbox worker container. |
| `SANDBOX_TMPFS_SIZE` | String | `50m` | Tmpfs size mounted into each sandbox worker container. |
| `SANDBOX_RUNTIME` | String | `nsjail` | Sandbox runtime. The current executor supports only `nsjail`. |

## `[redis]`

| Field | Type | Default / example | Description |
| --- | --- | --- | --- |
| `REDIS_HOST` | String | `redis` or `localhost` | Redis hostname used by the API. |
| `REDIS_PORT` | Integer | `6379` | Redis port exposed by Docker Compose and used by the API. |
| `REDIS_PASSWORD` | String | 64 hex chars | Redis password used by the Redis container and API. Generate with `python -c "import os; print(os.urandom(32).hex())"`. Treat as secret. |

## `[database]`

| Field | Type | Default / example | Description |
| --- | --- | --- | --- |
| `POSTGRES_DB` | String | `postgres` | PostgreSQL database name. |
| `POSTGRES_USER` | String | `postgres` | PostgreSQL username. |
| `POSTGRES_PASSWORD` | String | generated value | PostgreSQL password. Treat as secret. |
| `POSTGRES_HOST` | String | `db` or `localhost` | PostgreSQL host used by the API. Use `db` in Docker Compose and `localhost` for local development. |
| `POSTGRES_PORT` | Integer | `5432` | PostgreSQL port exposed by Docker Compose and used by the API. |
| `DATABASE_POOL_SIZE` | Integer | `10` | SQLAlchemy async connection pool size. |
| `DATABASE_MAX_OVERFLOW` | Integer | `20` | Maximum SQLAlchemy overflow connections above `DATABASE_POOL_SIZE`. |
| `POSTGRES_SHARED_BUFFERS` | String | `4GB` | PostgreSQL `shared_buffers` setting passed to the database container. Tune to available memory. |
| `POSTGRES_EFFECTIVE_CACHE_SIZE` | String | `12GB` | PostgreSQL `effective_cache_size` planner setting. Tune to available memory. |
| `POSTGRES_WORK_MEM` | String | `32MB` | PostgreSQL `work_mem` setting per operation. |
| `POSTGRES_MAINTENANCE_WORK_MEM` | String | `1GB` | PostgreSQL memory for maintenance operations such as vacuum and index creation. |
| `POSTGRES_RANDOM_PAGE_COST` | Number | `1.1` | PostgreSQL planner random page cost. Lower values favor index usage on SSDs. |
| `POSTGRES_MAX_WORKER_PROCESSES` | Integer | `8` | PostgreSQL maximum worker processes. |
| `POSTGRES_MAX_PARALLEL_WORKERS_PER_GATHER` | Integer | `4` | PostgreSQL parallel workers per gather operation. |
| `POSTGRES_MAX_PARALLEL_WORKERS` | Integer | `8` | PostgreSQL total parallel workers. |
| `POSTGRES_LOG_MIN_DURATION_STATEMENT` | String | `250ms` | Logs PostgreSQL statements slower than this threshold. |
| `POSTGRES_LOG_LOCK_WAITS` | String | `on` | Enables PostgreSQL lock-wait logging when set to `on`. |

## `[neo4j]`

| Field | Type | Default / example | Description |
| --- | --- | --- | --- |
| `NEO4J_USER` | String | `neo4j` | Username used by healthchecks and API connections. Docker Compose currently creates the built-in `neo4j` user via `NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}`, so keep this as `neo4j` unless Compose is changed too. |
| `NEO4J_PASSWORD` | String | generated value | Neo4j password used by the database container and API. Treat as secret. |
| `NEO4J_HOST` | String | `neo4j` or `localhost` | Neo4j hostname used by the API. Use `neo4j` in Docker Compose and `localhost` for local development. |
| `NEO4J_BOLT_PORT` | Integer | `7687` | Neo4j Bolt port exposed by Docker Compose and used by the API. |
| `NEO4J_BOLT_ADDRESS` | String | `0.0.0.0:7687` | Neo4j internal Bolt listen address. Keep in sync with `NEO4J_BOLT_PORT` when changing ports. |
| `NEO4J_HTTP_PORT` | Integer | `7474` | Neo4j HTTP UI/API port exposed by Docker Compose. |
| `NEO4J_HTTP_ADDRESS` | String | `0.0.0.0:7474` | Neo4j internal HTTP listen address. Keep in sync with `NEO4J_HTTP_PORT` when changing ports. |

## `[github]`

These values configure GitHub repository/account integration from the app settings flow. They are separate from `NUXT_OAUTH_GITHUB_*`, which configures login OAuth.

| Field | Type | Default / example | Description |
| --- | --- | --- | --- |
| `GITHUB_CLIENT_ID` | String | `""` | GitHub OAuth app client ID for GitHub account/repository integration. |
| `GITHUB_REDIRECT_URI` | String | `http://localhost:3000/settings?tab=github` | Redirect URI configured in the GitHub OAuth app for repository integration. |
| `GITHUB_CLIENT_SECRET` | String | `""` | GitHub OAuth app client secret for repository integration. Treat as secret. |

## `[sentry]`

| Field | Type | Default / example | Description |
| --- | --- | --- | --- |
| `SENTRY_DSN` | String | `""` | Optional Sentry DSN for backend monitoring and frontend public Sentry configuration. Leave empty to disable Sentry. Treat private DSNs as secret. |

## `[email]`

| Field | Type | Default / example | Description |
| --- | --- | --- | --- |
| `SMTP_SERVER` | String | `smtp.example.com` | SMTP server hostname used for email delivery. |
| `SMTP_PORT` | Integer | `587` | SMTP server port. |
| `SMTP_USERNAME` | String | `""` | SMTP username. Leave empty only if the server allows unauthenticated delivery. |
| `SMTP_PASSWORD` | String | `""` | SMTP password. Treat as secret. |
| `SMTP_AUTH_PROTOCOL` | String | `TLS` | SMTP connection mode. `SSL` uses implicit SSL, `STARTTLS` upgrades with STARTTLS, and any other value including the example `TLS` uses a plain SMTP connection before login. |
| `SMTP_FROM_EMAIL` | String | `""` | Sender address used for outbound emails. |

## Generated Or Advanced Variables

These variables are used by Compose or application code but are not regular TOML fields in the current examples.

| Variable | Source | Description |
| --- | --- | --- |
| `SANDBOX_WORKER_IMAGE` | Generated by `docker/run.sh` | Image tag passed to the sandbox manager for worker containers. Direct `docker compose` usage must provide it manually. |
| `NUXT_PUBLIC_SENTRY_DSN` | Derived from `SENTRY_DSN` in Compose | Public frontend Sentry DSN passed to Nuxt. Configure `SENTRY_DSN` instead. |
| `NUXT_PUBLIC_VERSION` | Build/dev environment | Optional frontend version string. Defaults to `development` in Nuxt when unset. |
| `IMAGE_TAG` | Shell/Compose environment | Production image tag used by `docker/docker-compose.prod.yml`. Defaults to `latest`. |
| `GOOGLE_CLIENT_ID` | Optional backend environment | Additional Google OAuth client ID accepted by the backend for ID token validation. `NUXT_OAUTH_GOOGLE_CLIENT_ID` is already documented in `[ui]`. |
| `REDIS_ANNOTATIONS_TTL_SECONDS` | Optional backend environment | Redis TTL for annotations. Defaults to 30 days. |
| `REDIS_PENDING_TOOL_CONTINUATION_TTL_SECONDS` | Optional backend environment | Redis TTL for pending tool continuation state. Defaults to 24 hours. |
| `MERMAID_VALIDATOR_SCRIPT` | Optional backend environment | Path to an optional Mermaid validator script. When unset, Mermaid validation falls back to built-in behavior. |
