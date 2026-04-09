# Meridian API - Developer README

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-005571?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/) [![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/) [![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org/) [![Neo4j](https://img.shields.io/badge/Neo4j-5-92D92F?logo=neo4j&logoColor=white)](https://neo4j.com/) [![Redis](https://img.shields.io/badge/Redis-7-DC2626?logo=redis&logoColor=white)](https://redis.io/)

This folder contains the **complete backend API** for Meridian, built with **FastAPI**, **Python 3.11**, and a fully asynchronous stack. It powers graph persistence, AI orchestration via OpenRouter, real-time streaming, authentication, file handling, Git integrations, and advanced tooling (web search, link extraction).

## Table of Contents

- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Development Commands](#development-commands)
- [Core Concepts](#core-concepts)
  - [Graph Engine](#graph-engine)
  - [Streaming & Execution](#streaming--execution)
  - [Authentication](#authentication)
  - [Tooling & Integrations](#tooling--integrations)
  - [Caching & Annotations](#caching--annotations)
- [Routers Overview](#routers-overview)
- [Services Overview](#services-overview)
- [Database Models](#database-models)
- [Migrations](#migrations)
- [Building & Deployment](#building--deployment)

## Key Features

- **Graph Persistence**: Hybrid storage with **PostgreSQL** (structured data) + **Neo4j** (nodes/edges traversal, execution plans).
- **Real-time Streaming**: WebSocket-driven AI responses with tool calls (web search, page extraction, code execution), reasoning tags (`[THINK]`), and usage tracking.
- **Node System**: Supports **Text-to-Text**, **Parallelization** (multi-LLM), **Routing**, **Context Merger**, **GitHub/GitLab**, attachments (PDFs via OpenRouter).
- **Advanced Execution**: Upstream/downstream plans, conditional routing, branch merging, parallel querying.
- **Authentication**: JWT access tokens + refresh token rotation (replay attack detection), OAuth (GitHub/Google/userpass).
- **File & Repo Handling**: Secure uploads, PDF annotation caching (Redis), Git clone/pull with SSH/HTTPS.
- **Sandbox Artifacts**: Code execution can now persist bounded files written to `MERIDIAN_OUTPUT_DIR` and surface them back to chat as inline images or downloads.
- **Metered Tooling**: Web search (SearxNG/Google Custom fallback), link extraction with limits per plan (free/premium).
- **Enterprise Features**: Configurable per-graph/user, Sentry monitoring, async Redis for annotations/hash maps.
- **Rate Limiting & Security**: SlowAPI, CORS, encrypted tokens (AES-GCM), CSRF-safe WebSockets.

## Tech Stack

| Category | Technologies |
|----------|--------------|
| **Framework** | FastAPI (async) |
| **Language** | Python 3.11 (asyncio) |
| **Databases** | PostgreSQL (SQLModel/Alembic), Neo4j (async driver), Redis (annotations) |
| **AI Provider** | OpenRouter.ai (streaming, tools, reasoning) |
| **Auth** | JWT (PyJWT), OAuth2, bcrypt |
| **Git** | GitPython alternatives (subprocess), SSH key temp files |
| **Web Scraping** | curl-cffi (proxies), BeautifulSoup/markdownify, Playwright fallback |
| **Caching** | Redis (file annotations, hash maps) |
| **Monitoring** | Sentry (traces, profiles) |
| **Utils** | Pydantic v2, httpx (async HTTP), aiofiles |
| **Dev Tools** | Black, isort, mypy, flake8, Alembic |

## Project Structure

```plaintext
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

# Run dev server with hot reload, excluding runtime-generated files
./run-dev.sh

API docs: `http://localhost:8000/docs`

### Dev checks

```bash
pip install -r requirements-dev.txt
./run-linter.sh
```

`fastapi dev main.py` is not the recommended command here. Sandbox-generated Python files under
`app/data/user_files/.../generated_files/...` can trigger unnecessary backend reloads. `./run-dev.sh`
uses `uvicorn --reload-exclude` so hot reload stays focused on source changes.

**API Docs:** `http://localhost:8000/docs` (Swagger UI).

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

- **WebSocket Single Endpoint**: `/ws/chat/{client_id}?token=...` handles all streams (cancel via msg).
- **Async Streaming**: OpenRouter SSE → chunked WS, tool calls (search/fetch/code execution) looped.
- **Node Types**: Text-to-Text (chat), Parallel (multi-LLM+agg), Routing (JSON select), ContextMerger (branches).

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
