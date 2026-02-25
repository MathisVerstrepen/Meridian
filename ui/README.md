# Meridian UI Frontend

Nuxt 4 frontend for Meridian. This app provides the canvas editor, chat UX, settings/admin panels, auth pages, and a Nitro server layer that proxies authenticated requests to the Python API.

## Scope

`ui/` contains:

- The Nuxt app (`app/`) with pages, layouts, components, composables, stores, and types.
- A Nitro server layer (`server/`) for session handling, OAuth handlers, auth cookie management, and API proxying.
- Frontend build/runtime configuration (`nuxt.config.ts`, Tailwind/CSS, ESLint, pnpm scripts).

## Tech Stack

- Nuxt `^4.1.3` + Vue 3
- TypeScript (Nuxt-generated tsconfig, `strict: false` in Nuxt config)
- Pinia stores
- Vue Flow (`@vue-flow/core` + controls/resizer/additional-components)
- Tailwind CSS v4 (+ typography + headlessui plugins)
- `nuxt-auth-utils` (session + OAuth handlers)
- Marked + Shiki + KaTeX + Mermaid (Markdown rendering pipeline)

## Architecture

### 1) Client app (`app/`)

- Route pages:
  - `/` home
  - `/graph/[id]` canvas/editor
  - `/settings` settings/admin
  - `/auth/login`, `/auth/register`, `/auth/verify`, `/auth/update-email`
- Main layouts:
  - `canvas` (sidebar + mountpoints)
  - `auth` (auth shell)
  - `blank` (minimal)

### 2) Nitro server layer (`server/`)

The frontend does not directly send bearer tokens from browser JS. Instead:

- Access token is stored in HttpOnly cookie `auth_token`.
- Most frontend API calls go to same-origin `/api/*`.
- `server/api/[...].ts` reads `auth_token` and proxies to FastAPI with:
  - `Authorization: Bearer <auth_token>`
- Auth/session routes are implemented under `server/api/auth/*`.

### 3) Backend communication model

- HTTP: same-origin `/api/*` from client -> Nitro proxy -> FastAPI.
- WebSocket: UI requests token via `/api/auth/ws-token`, then opens backend WS directly:
  - `ws(s)://<NUXT_PUBLIC_API_BASE_URL>/ws/chat/{clientId}?token=<jwt>`

## Authentication and Session Flow

### Cookies used

- `auth_token`
  - HttpOnly, SameSite `strict`, path `/`, maxAge 15 minutes
- `refresh_token`
  - HttpOnly, SameSite `strict`, path `/api/auth/refresh`, maxAge 30 days

`secure` is enabled when `NODE_ENV=production`.

### Auth routes in Nitro

- `POST /api/auth/login`
- `POST /api/auth/register`
- `POST /api/auth/verify`
- `POST /api/auth/resend`
- `POST /api/auth/update-email`
- `POST /api/auth/reset-password`
- `POST /api/auth/refresh`
- `POST /api/auth/ack-welcome`
- `GET /api/auth/ws-token`
- `GET /api/auth/github` (OAuth handler)
- `GET /api/auth/google` (OAuth handler)

### Route protection

`app/middleware/auth.ts`:

1. Loads session (`useUserSession().fetch()`).
2. If not logged in, tries `/api/auth/refresh` once.
3. Redirects to `/auth/login` if still unauthenticated.
4. For legacy `userpass` accounts with missing/unverified email, clears session and redirects to `/auth/update-email`.

### Session sync hook

`server/plugins/session.ts` refreshes user profile from backend (`/users/me`) whenever session is fetched, so avatar/name/plan/admin flags stay current.

## Runtime Configuration and Env Vars

Defined in `nuxt.config.ts`:

- `runtimeConfig.apiInternalBaseUrl`
  - from `NUXT_API_INTERNAL_BASE_URL`
  - used by Nitro server routes to call FastAPI
- `runtimeConfig.public.apiBaseUrl`
  - from `NUXT_PUBLIC_API_BASE_URL`
  - used by client for WS endpoint construction and select direct links
- `runtimeConfig.public.isOauthDisabled`
  - from `NUXT_PUBLIC_IS_OAUTH_DISABLED`
- `runtimeConfig.public.version`
  - from `NUXT_PUBLIC_VERSION`
- `runtimeConfig.session.maxAge`
  - 30 days

Common UI env vars (from docker config):

- `NUXT_API_INTERNAL_BASE_URL`
- `NUXT_PUBLIC_API_BASE_URL`
- `NUXT_SESSION_PASSWORD`
- `NUXT_PUBLIC_IS_OAUTH_DISABLED`
- `NUXT_PUBLIC_VERSION`
- `NUXT_OAUTH_GITHUB_CLIENT_ID`
- `NUXT_OAUTH_GITHUB_CLIENT_SECRET`
- `NUXT_OAUTH_GOOGLE_CLIENT_ID`
- `NUXT_OAUTH_GOOGLE_CLIENT_SECRET`

## Local Development

```bash
cd ui
pnpm install
pnpm dev
```

Available scripts:

- `pnpm dev`
- `pnpm build`
- `pnpm generate`
- `pnpm preview`
- `pnpm lint`
- `pnpm lint:fix`

No dedicated test script is currently defined in `package.json`.

## Key App Runtime Behavior

### App bootstrap (`app/app.vue`)

- Applies theme/accent from `localStorage` early (`theme`, `accentColor`), toggles `dark` class.
- Loads essentials once per route lifecycle:
  - models (`/api/models`)
  - user settings (`/api/user/settings`)
  - GitHub connection status (background)
- Initializes stores and shared UI mountpoints.

### Theme system

- Defined in `app/assets/css/main.css` with Tailwind v4 `@theme` tokens.
- Theme classes:
  - `theme-standard`
  - `theme-light`
  - `theme-dark`
  - `theme-oled`
- Accent color is controlled via CSS variable `--color-ember-glow`.

### Canvas system (`/graph/[id]`)

- Uses Vue Flow instance id: `main-graph-${graphId}`.
- Handles drag/drop block creation, custom edges, copy/paste, grouping, overlap resolution, execution plan dispatch, autosave state, and node-level streaming.
- `useBlocks` defines node palettes and defaults from user settings.

Node families in current UI model:

- Input: `prompt`, `filePrompt`, `github`
- Generator: `textToText`, `parallelization`, `routing`
- Utility: `contextMerger`

### Home (`/`)

- Loads graphs/folders/workspaces.
- Enforces free-plan graph limit in UI (`PLAN_LIMITS.FREE.MAX_GRAPHS = 5`).
- Can create:
  - new canvas
  - new chat canvas
  - temporary canvas

### Settings (`/settings`)

Tab groups are built from live settings data and user role:

- General
- Account
- Appearance
- Models
  - Dropdown
  - System Prompt
- Blocks
  - Prompt Templates
  - Attachment
  - Parallelization
  - Routing
  - GitHub
  - Context Merger
- Tools
  - Web Search
  - Link Extraction
  - Image Generation
- Admin Users (admin only)

## API Integration Surface (Frontend)

Most application calls are in `app/composables/useAPI.ts` and target same-origin `/api/*`.

Main groups:

- Graphs:
  - list/get/create/update/delete/pin/persist/config/search/backup/restore/move
- Chat:
  - history fetch
  - execution plan fetch
- Models/settings/user:
  - model catalog
  - user settings read/write
  - update username
  - avatar upload
  - usage stats
  - delete account
- Files:
  - root/list/upload/create folder/rename/delete/view/download/generated images
- Prompt templates:
  - library/marketplace/bookmarks/CRUD/reorder/bookmark toggle
- Providers/repos:
  - GitHub/GitLab connect status
  - repository list/clone/branches/tree/content/pull/issues/commit-state
- Workspaces/folders:
  - CRUD

## WebSocket Streaming Contract (UI Side)

`useWebSocket` and `useStreamStore` handle WS lifecycle and state.

Outgoing message types:

- `start_stream`
- `regenerate_title`
- `cancel_stream`

Incoming message types handled by UI:

- `stream_chunk`
- `stream_end`
- `stream_error`
- `routing_response`
- `title_response`
- `usage_data_update`
- `node_data_update`

Reconnection:

- Exponential backoff
- up to 10 reconnect attempts
- no reconnect for close codes `1000` or `1008`

## State and Composition Patterns

### Core stores

- `settings`: all user settings + save trigger + change tracking
- `model`: model list, sort/filter, fallback model behavior
- `chat`: per-node chat sessions, open/close/load/refresh
- `stream`: stream session registry, callbacks, chunk buffering/flush
- `canvasSave`: save status and deduplicated save promises
- `repository`: cached repository listing
- `promptTemplate`: template library/marketplace/bookmarks + request dedupe
- `github` / `gitlab`: provider connection state
- `usageStore`: metered usage state

### Core composables

- `useAPI`: HTTP wrapper + 401 refresh retry + typed endpoint helpers
- `useWebSocket`: singleton WS client
- `useGraphEvents`: app-level event bus for graph/editor interactions
- `useNodeRegistry`: execution/stop registry for node components
- `useGraphActions`, `useGraphChat`, `useGraphDragAndDrop`: canvas mechanics
- `useChatGenerator`: chat generation/regeneration orchestration
- `useFiles` + `fileManager/*`: upload/browser/download/rename/delete flows

## Markdown/Code/Diagram Rendering Pipeline

### Worker-based markdown parsing

- Worker file: `app/assets/worker/marked.worker.ts`
- Accessed via singleton composable: `useMarkedWorker`
- Handles:
  - Marked parsing
  - Shiki highlighting (with caching and lazy language loading)
  - KaTeX rendering (inline and block)
  - Mermaid code block passthrough for runtime rendering

### Client-side post processing

`useMarkdownProcessor`:

- Parses custom stream tags (`[THINK]`, `[WEB_SEARCH]`, `<fetch_url>`, errors)
- Enhances rendered output:
  - copy buttons on code blocks
  - fullscreen controls for Mermaid blocks

### Mermaid plugin

`app/plugins/mermaid.client.ts` initializes Mermaid globally with `securityLevel: 'loose'` and dark theme defaults.

## File and Asset Notes

- File icon mapping logic is in `useFileIcons.ts` and is sourced from `vscode-material-icon-theme` metadata.
- Favicon assets are under `public/favicon`.
- Auth background artwork is in `app/assets/img/login_bg.*`.

## Deployment Notes

- In production, set both internal and public API URLs correctly:
  - internal for Nitro server -> API container
  - public for browser -> externally reachable API
- OAuth buttons on login are controlled by `NUXT_PUBLIC_IS_OAUTH_DISABLED`.
- Session security depends on `NUXT_SESSION_PASSWORD` and production cookie `secure` behavior.
