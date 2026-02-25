# Meridian API Backend

Backend service for Meridian, built with FastAPI and an async stack around PostgreSQL, Neo4j, Redis, and OpenRouter.

## Scope

This `api/` package is responsible for:

- Authentication, sessions, and user/account settings.
- Graph/canvas persistence and traversal (nodes, edges, execution planning).
- Chat and generation streaming over WebSocket.
- File storage (uploads, generated images, avatars) and storage quota enforcement.
- Tool calling (web search, link extraction, image generation/editing).
- Git provider integrations (GitHub/GitLab) and repository operations.
- Prompt template library/marketplace/bookmarks.

## Stack

- Python 3.11
- FastAPI (`fastapi[standard]`)
- PostgreSQL + SQLModel + Alembic
- Neo4j async driver
- Redis (annotation/hash caching)
- OpenRouter API
- httpx, aiofiles, curl-cffi, patchright (Playwright-compatible), Pillow

## Runtime Architecture

### App bootstrap (`app/main.py`)

At startup (lifespan):

1. Loads env vars from `../../docker/env/.env.local` when `ENV=dev`.
2. Optionally initializes Sentry (`SENTRY_DSN`).
3. Creates PostgreSQL async engine.
4. Optionally creates initial users from `USERPASS`.
5. Creates user root folders + default settings for newly created users.
6. Creates Neo4j async driver + GNode index.
7. Requires `MASTER_OPEN_ROUTER_API_KEY` (hard fail if missing).
8. Starts hourly background jobs:
   - delete temporary graphs older than 1 hour
   - refresh OpenRouter model catalog
9. Creates shared `httpx.AsyncClient` and Redis manager.
10. Mounts static files from `/static` -> `data/`.

Other runtime behavior:

- Global exception handler returns a generic 500 payload and reports to Sentry.
- CORS:
  - `ENV=dev`: `*`
  - otherwise `ALLOW_CORS_ORIGINS` (comma-separated)

## Key Directories

```text
api/
├── app/
│   ├── main.py
│   ├── routers/                # HTTP + WebSocket endpoints
│   ├── services/               # business logic, OpenRouter, tools, git, auth
│   ├── database/
│   │   ├── pg/                 # SQLModel models + CRUD
│   │   ├── neo4j/              # traversal and execution plans
│   │   └── redis/              # annotation/hash caches
│   ├── models/                 # DTOs and enums
│   ├── const/                  # defaults, prompts, plan limits
│   └── templates/              # email template(s)
├── migrations/                 # Alembic migrations
├── alembic.ini
├── requirements.txt
├── requirements-dev.txt
└── run-linter.sh
```

## Local Development

### 1) Start dependencies

From repo root, start the dev stack (Postgres/Neo4j/Redis/etc.):

```bash
cd docker
./run.sh dev -d
```

### 2) Install backend deps

```bash
cd ../api
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3) Apply migrations

```bash
alembic upgrade head
```

### 4) Run API

```bash
cd app
fastapi dev main.py --host 0.0.0.0 --port 8000
```

API docs: `http://localhost:8000/docs`

### Dev checks

```bash
pip install -r requirements-dev.txt
./run-linter.sh
```

## Authentication Model

### OpenRouter keys

- `MASTER_OPEN_ROUTER_API_KEY` is required for backend startup and model catalog refresh.
- Actual generation requests use each user's encrypted `account.openRouterApiKey` from settings. If it is missing, generation requests fail.

### Access + refresh

- Access token: JWT HS256 (`JWT_SECRET_KEY`), 15 minutes.
- Refresh token: opaque token stored in DB, 30 days, rotation on use.
- Replay protection: reused/compromised refresh token triggers user-wide refresh token invalidation.

### Account flows

- User/pass registration with email verification code.
- Resend verification code.
- Update unverified email.
- Login with optional `rememberMe` (controls refresh token issuance).
- Password reset (invalidates all refresh tokens).
- OAuth sync endpoint for `google`, `github`, `userpass` identity sync from frontend.

### Security details

- Provider/API keys are encrypted with AES-GCM (`BACKEND_SECRET`).
- Passwords are hashed with bcrypt.
- WebSocket auth uses `token` query parameter validated as JWT.

## API Surface (Current)

All routes are mounted at root (no FastAPI global prefix).

Authentication behavior:

- Most routes require `Authorization: Bearer <accessToken>`.
- Public/unauthenticated routes are primarily auth bootstrap endpoints (`/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/verify-email`, `/auth/resend-verification`, `/auth/update-unverified-email`) plus `/auth/github/login` and `/`.
- Repository branch/tree/content/pull routes currently do not enforce auth dependencies in router code.
- WebSocket chat authenticates with `token` query parameter instead of Authorization header.

### Core/system

- `GET /` health-like placeholder (`{"Hello":"World"}`)
- `GET /models` list OpenRouter models (cached in app state)

### Chat / execution

- `WS /ws/chat/{client_id}?token=...`
- `GET /chat/{graph_id}/{node_id}/execution-plan/{direction}`
- `GET /chat/{graph_id}/{node_id}`

`direction`: `upstream | downstream | all | multiple`

### Graphs, folders, workspaces

- `GET /graphs`
- `GET /graph/{graph_id}`
- `POST /graph/create`
- `POST /graph/{graph_id}/update`
- `POST /graph/{graph_id}/update-name`
- `POST /graph/{graph_id}/pin/{pinned}`
- `POST /graph/{graph_id}/persist`
- `POST /graph/{graph_id}/update-config`
- `DELETE /graph/{graph_id}`
- `POST /graph/{graph_id}/search-node`
- `GET /graph/{graph_id}/backup`
- `POST /graph/backup`
- `GET /folders`
- `POST /folders`
- `PATCH /folders/{folder_id}`
- `DELETE /folders/{folder_id}`
- `POST /graph/{graph_id}/move`
- `GET /workspaces`
- `POST /workspaces`
- `PATCH /workspaces/{workspace_id}`
- `DELETE /workspaces/{workspace_id}`

### Users + auth + admin

- `GET /users/me`
- `POST /auth/register`
- `POST /auth/verify-email`
- `POST /auth/resend-verification`
- `POST /auth/update-unverified-email`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/sync-user/{provider}`
- `POST /auth/reset-password`
- `GET /user/settings`
- `POST /user/settings`
- `POST /user/avatar`
- `GET /user/avatar`
- `POST /user/update-name`
- `POST /user/ack-welcome`
- `GET /user/usage`
- `DELETE /user/me`
- `GET /admin/users`
- `DELETE /admin/users/{target_user_id}`

### Files

All under `/files`:

- `POST /files/folder`
- `POST /files/upload`
- `GET /files/root`
- `GET /files/list/{folder_id}`
- `GET /files/generated_images`
- `GET /files/view/{file_id}`
- `PATCH /files/{item_id}/rename`
- `DELETE /files/{item_id}`

### Prompt templates

All under `/prompt-templates`:

- `GET /prompt-templates/library`
- `GET /prompt-templates/marketplace`
- `GET /prompt-templates/library/combined`
- `GET /prompt-templates/bookmarks`
- `PUT /prompt-templates/reorder`
- `GET /prompt-templates/{template_id}`
- `POST /prompt-templates`
- `PUT /prompt-templates/{template_id}`
- `DELETE /prompt-templates/{template_id}`
- `POST /prompt-templates/{template_id}/bookmark`
- `DELETE /prompt-templates/{template_id}/bookmark`

### GitHub / GitLab connectivity

- `GET /auth/github/login`
- `POST /auth/github/callback`
- `POST /auth/github/disconnect`
- `GET /auth/github/status`
- `GET /github/repos`

- `POST /auth/gitlab/connect`
- `POST /auth/gitlab/disconnect`
- `GET /auth/gitlab/status`

### Repository operations

- `GET /repositories`
- `POST /repositories/clone`
- `GET /repositories/{encoded_provider}/{project_path:path}/branches`
- `GET /repositories/{encoded_provider}/{project_path:path}/tree`
- `GET /repositories/{encoded_provider}/{project_path:path}/content/{file_path:path}`
- `POST /repositories/{encoded_provider}/{project_path:path}/pull`
- `GET /repositories/{encoded_provider}/{project_path:path}/issues`
- `GET /repositories/{encoded_provider}/{project_path:path}/commit-state`

## WebSocket Protocol (`/ws/chat/{client_id}`)

### Incoming messages

- `start_stream`
  - payload: `GenerateRequest`
  - fields: `graph_id`, `node_id`, `model`, optional `modelId`, `stream_type`, `title`
- `regenerate_title`
  - payload: `{ graph_id, strategy? }`
- `cancel_stream`
  - payload: `{ node_id }`

### Outgoing messages (main)

- `stream_chunk`
- `stream_end`
- `stream_error`
- `routing_response`
- `usage_data_update`
- `node_data_update` (ContextMerger metadata updates)

Stream content may include markers such as `[THINK]`, `[!THINK]`, `[WEB_SEARCH]`, `[!WEB_SEARCH]`, `[IMAGE_GEN]`, `[!IMAGE_GEN]`, and `[ERROR]...`.

## Data Model Highlights

PostgreSQL tables (main):

- `users`, `verification_tokens`, `refresh_tokens`, `used_refresh_tokens`, `provider_tokens`
- `settings`
- `graphs`, `nodes`, `edges`
- `workspaces`, `folders`
- `files`, `user_storage_usage`
- `prompt_templates`, `template_bookmarks`
- `repositories`
- `user_query_usage`

Neo4j:

- `GNode` + `CONNECTS_TO`, keyed by `unique_id = "{graph_id}:{node_id}"`.

Redis:

- `annotation:{remote_hash}`
- `hash_map:{local_hash}`

## Limits and Plan Enforcement

From `const/plans.py`:

- Free:
  - web_search: 0/month
  - link_extraction: 0/month
  - storage: 50 MB
- Premium:
  - web_search: 200/month
  - link_extraction: 1000/month
  - storage: 5 GB

Additional enforcement:

- Free users: max 5 non-temporary canvases.
- Free users: cannot use `github` premium node type.

## Tools and Integrations

### Web search tool

- Primary: SearxNG (`SEARXNG_URL`, default `localhost:8888`)
- Fallback: Google Custom Search (`GOOGLE_SEARCH_API_KEY` + `GOOGLE_CSE_ID`)
- Per-user usage metering by billing period.

### Link extraction tool

- Attempts in order:
  1. direct curl-cffi fetch
  2. proxy rotation via `proxies.txt`
  3. browser fallback via patchright (Playwright-compatible)
- Converts content to markdown (special handling for Reddit JSON and arXiv).
- Per-user usage metering by billing period.

### Image generation/editing tool

- Uses OpenRouter chat completions with image modalities.
- Saves generated/edited images under user storage (`generated_images/`) and indexes in `files` table.

## Environment Variables

### Required for app startup

- `MASTER_OPEN_ROUTER_API_KEY`
- `JWT_SECRET_KEY`
- `BACKEND_SECRET` (64-char hex)
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `NEO4J_HOST`
- `NEO4J_BOLT_PORT`
- `NEO4J_USER`
- `NEO4J_PASSWORD`

### Common optional

- `ENV` (`dev` enables `.env.local` loading and permissive CORS)
- `ALLOW_CORS_ORIGINS`
- `SENTRY_DSN`
- `USERPASS` (bootstrap users, format: `user1:pass1,user2:pass2`)
- `DATABASE_ECHO`, `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW`
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, `REDIS_ANNOTATIONS_TTL_SECONDS`

### Feature-specific optional

- GitHub OAuth: `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `GITHUB_REDIRECT_URI`
- Search fallback: `GOOGLE_SEARCH_API_KEY`, `GOOGLE_CSE_ID`
- Search primary: `SEARXNG_URL`
- Email verification delivery: `SMTP_SERVER`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `SMTP_AUTH_PROTOCOL`

## Migrations

- Alembic migration files are under `migrations/versions`.
- Current migration set includes graph/workspace/folder, prompt templates/bookmarks, user usage/storage, verification, pin/temporary/content-hash fields, and related FK/cascade updates.

Run:

```bash
cd api
alembic upgrade head
```

## Operational Notes

- User files live under `api/app/data/user_files/{user_id}`.
- Cloned repositories live under `api/app/data/cloned_repos/{provider}/{project_path}`.
- Static mount `/static` exposes `api/app/data`.
- Temporary graphs are auto-pruned hourly if stale for >1 hour.
- OpenRouter model catalog is refreshed hourly and cached in app state.
