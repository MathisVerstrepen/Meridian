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
- **Real-time Streaming**: WebSocket-driven AI responses with tool calls (web search, page extraction), reasoning tags (`[THINK]`), and usage tracking.
- **Node System**: Supports **Text-to-Text**, **Parallelization** (multi-LLM), **Routing**, **Context Merger**, **GitHub/GitLab**, attachments (PDFs via OpenRouter).
- **Advanced Execution**: Upstream/downstream plans, conditional routing, branch merging, parallel querying.
- **Authentication**: JWT access tokens + refresh token rotation (replay attack detection), OAuth (GitHub/Google/userpass).
- **File & Repo Handling**: Secure uploads, PDF annotation caching (Redis), Git clone/pull with SSH/HTTPS.
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
├── app/                    # Main app source
│   ├── main.py             # FastAPI app + lifespan (DB init, crons)
│   ├── const/              # Constants
│   │   ├── prompts.py      # System prompts (routing, summarization, Mermaid)
│   │   ├── settings.py     # Defaults (node wheel, routes, tools)
│   │   └── plans.py        # Usage limits (free/premium)
│   ├── database/           # DB layers
│   │   ├── pg/             # PostgreSQL (SQLModel)
│   │   │   ├── core.py     # Async engine
│   │   │   ├── models.py   # Schemas (Graph, Node, Edge, User, Files, etc.)
│   │   │   ├── file_ops/   # File CRUD (recursive delete)
│   │   │   ├── graph_ops/  # Graph CRUD (neo sync, config)
│   │   │   ├── settings_ops/
│   │   │   ├── token_ops/  # Refresh/Provider tokens
│   │   │   └── user_ops/   # Usage metering
│   │   └── neo4j/          # Neo4j graph engine
│   │       ├── core.py     # Async driver + indexes
│   │       └── crud.py     # Traversal (ancestors, plans, search)
│   ├── models/             # Pydantic DTOs
│   │   ├── auth.py         # UserSync, OAuth
│   │   ├── chatDTO.py      # GenerateRequest, EffortEnum
│   │   ├── message.py      # Message, NodeTypeEnum, UsageData
│   │   └── usersDTO.py     # SettingsDTO (full config)
│   ├── routers/            # API endpoints
│   │   ├── chat.py         # WS streaming, execution plans
│   │   ├── files.py        # Upload/list/delete (recursive)
│   │   ├── github.py       # OAuth, repos, status
│   │   ├── gitlab.py       # PAT/SSH connect/disconnect
│   │   ├── graph.py        # CRUD, search, backup/restore
│   │   ├── models.py       # OpenRouter models list
│   │   ├── repository.py   # Clone/pull/tree/content (GitHub/GitLab)
│   │   └── users.py        # Settings, usage, avatar
│   ├── services/           # Business logic
│   │   ├── auth.py         # JWT, refresh rotation
│   │   ├── connection_manager.py # WS tasks
│   │   ├── context_merger_service.py # Branch merging/summarization
│   │   ├── crypto.py       # AES-GCM (tokens), bcrypt
│   │   ├── files.py        # Disk ops, hash calc
│   │   ├── git_service.py  # Clone/pull/tree (locked)
│   │   ├── github.py       # Token fetch, commit info
│   │   ├── gitlab_api_service.py # Repos/commits
│   │   ├── graph_service.py # Message history, plans, config
│   │   ├── node.py         # Node→Message, context extract
│   │   ├── openrouter.py   # Streaming/non-streaming, models
│   │   ├── proxies.py      # curl-cffi pool
│   │   ├── settings.py     # Prompt concat
│   │   ├── ssh_manager.py  # Temp SSH keys
│   │   └── stream.py       # WS propagation, tools
│   └── utils/              # Helpers
│       ├── helpers.py      # Env load
│       └── print.py        # Rich pydantic print
├── migrations/             # Alembic (PG schema)
├── alembic.ini
├── pyproject.toml          # Black/isort/mypy
├── requirements.txt        # Prod deps
└── requirements-dev.txt    # Linting/typing
```

## Quick Start

### Prerequisites

- Python **3.11+** (pyenv recommended)
- **Docker** (for PG/Neo4j/Redis dev setup)
- Git (for repo cloning)
- Backend DBs running (see root README: `./run.sh dev -d`)

### Installation

```bash
cd api
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### Development Commands

```bash
# Migrations (first run or after changes)
alembic upgrade head

# Run dev server (localhost:8000, /docs auto-open)
cd app
fastapi dev main.py --host 0.0.0.0 --port 8000

# Lint & format
pip install -r requirements-dev.txt
run-linter.sh  # Black + isort + flake8 + mypy

# Test migrations
alembic check
```

**API Docs:** `http://localhost:8000/docs` (Swagger UI).

## Core Concepts

### Graph Engine

- **Hybrid Storage**: PG for nodes/edges/config (SQLModel), Neo4j for traversal (ancestors, plans, search).
- **Unique IDs**: `graph_id:node_id` in Neo4j for isolation.
- **Execution Plans**: Upstream/downstream/all nodes → topological order with deps.

### Streaming & Execution

- **WebSocket Single Endpoint**: `/ws/chat/{client_id}?token=...` handles all streams (cancel via msg).
- **Async Streaming**: OpenRouter SSE → chunked WS, tool calls (search/fetch) looped.
- **Node Types**: Text-to-Text (chat), Parallel (multi-LLM+agg), Routing (JSON select), ContextMerger (branches).

### Authentication

- **JWT Access (15m)**: Stateless, user ID in `sub`.
- **Refresh Rotation (30d)**: DB-stored, replay detection → invalidate all.
- **OAuth**: GitHub/Google/userpass; provider tokens encrypted (AES-GCM).

### Tooling & Integrations

| Tool | Provider | Limits (Free/Premium) |
|------|----------|-----------------------|
| Web Search | SearxNG (fallback Google Custom) | 0/200 monthly |
| Link Extract | curl-cffi + markdownify + Playwright | 0/1000 monthly |

- **GitHub/GitLab**: Clone/pull (SSH/HTTPS), tree/content, commit sync.
- **Files**: Recursive FS (folders/files), PDF annotations (OpenRouter cached in Redis).

### Caching & Annotations

- **Redis**: File hash maps (`local→remote`), annotations (OpenRouter PDFs).
- **TTL**: 30 days (`REDIS_ANNOTATIONS_TTL_SECONDS`).

## Routers Overview

| Path | Description |
|------|-------------|
| `/graphs` | CRUD graphs (neo sync), search nodes, backup/restore |
| `/chat/{graph_id}/{node_id}` | WS streaming, execution plans |
| `/models` | OpenRouter models list (cached) |
| `/users` | Settings, usage, avatar upload, auth (login/refresh/OAuth) |
| `/files` | Upload/list/delete (recursive), root FS |
| `/auth/github` | OAuth connect/disconnect/repos/status |
| `/auth/gitlab` | PAT/SSH connect/disconnect/status |
| `/repositories` | List/clone/pull/tree/content (GitHub/GitLab) |

## Services Overview

| Name | Purpose |
|------|---------|
| `auth.py` | JWT/refresh, OAuth sync, password ops |
| `connection_manager.py` | WS tasks/cancel |
| `context_merger_service.py` | Branch merge/summarize (full/last_n/summary) |
| `crypto.py` | AES/bcrypt (tokens/passwords) |
| `files.py` | Disk/hash ops, root folder |
| `git_service.py` | Clone/pull/tree (locked) |
| `graph_service.py` | History/plans/config merge |
| `node.py` | Node→Message, context extract |
| `openrouter.py` | Streaming/non-streaming, models |
| `stream.py` | WS propagation, tools loop |

## Database Models

- **Graph**: Canvases (config, temporal/pinned).
- **Node/Edge**: Positions/data (JSONB), PK `(graph_id, id)`.
- **User**: Auth (OAuth/JWT), plan (free/premium), settings (JSONB).
- **Files**: FS tree (recursive), hash/indexed.
- **Tokens**: Refresh (rotation), Provider (encrypted).
- **QueryUsage**: Metered tools (per-period).

**Neo4j**: `GNode(unique_id, type)` + `CONNECTS_TO` edges.

## Migrations

Alembic-managed (PG only). Run `alembic upgrade head` after pulls.

## Building & Deployment

```bash
# Prod build (Docker)
# See root README: ./run.sh prod -d (pre-built) or build

# Local prod preview
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Env Vars**:

- `MASTER_OPEN_ROUTER_API_KEY`: OpenRouter master key.
- `JWT_SECRET_KEY`/`BACKEND_SECRET`: 64-char hex (auth/crypto).
- `SENTRY_DSN`: Optional monitoring.
- DB/Redis: From `config.local.toml` (dev).

**Docker**: Full-stack in root README (PG/Neo4j/Redis/API/UI).
