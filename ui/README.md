# Meridian UI - Developer README

[![Nuxt](https://img.shields.io/badge/Nuxt-00DC82?logo=nuxt.js&logoColor=white)](https://nuxt.com/) [![Vue 3](https://img.shields.io/badge/Vue-3.5-42B883?logo=vue.js&logoColor=white)](https://vuejs.org/) [![Tailwind CSS](https://img.shields.io/badge/Tailwind-38bdf8?logo=tailwindcss&logoColor=white)](https://tailwindcss.com/) [![Vue Flow](https://img.shields.io/badge/Vue_Flow-1.47-10B981?logo=vue.js&logoColor=white)](https://vueflow.dev/)

This folder contains the **complete frontend application** for Meridian, built with **Nuxt 4**, **Vue 3**, and a modern stack. It provides the visual graph canvas, chat interface, settings panels, and all UI interactions.

## Table of Contents

- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Development Commands](#development-commands)
- [Core Concepts](#core-concepts)
  - [Graph Canvas](#graph-canvas)
  - [Chat Integration](#chat-integration)
  - [Styling & Theming](#styling--theming)
  - [API Integration](#api-integration)
  - [State Management](#state-management)
- [Components Overview](#components-overview)
- [Composables Overview](#composables-overview)
- [Custom Tools](#custom-tools)
  - [Marked Web Worker](#marked-web-worker)
  - [Mermaid Rendering](#mermaid-rendering)
- [Building & Deployment](#building--deployment)

## Key Features

- **Interactive Graph Canvas**: Powered by [Vue Flow](https://vueflow.dev/) for drag-and-drop node editing, connections, and execution visualization.
- **Dual-View Chat**: Seamless chat interface integrated with the graph; supports branching, regeneration, and rich content (Markdown, LaTeX, code highlighting, Mermaid diagrams).
- **Node System**: Modular blocks for prompts, files/GitHub context, LLMs (Text-to-Text, Parallelization, Routing), and utilities (Context Merger).
- **Real-time Streaming**: WebSocket-driven AI responses with thinking steps, tool calls (web search, link extraction), and usage tracking.
- **Theming**: 4 themes (Standard, Light, GitHub Dark, OLED) with custom Tailwind colors and CSS variables.
- **File Handling**: Drag-and-drop uploads, GitHub repo integration, PDF processing.
- **Responsive & Accessible**: Headless UI components, keyboard navigation, ARIA labels.

## Tech Stack

| Category | Technologies |
|----------|--------------|
| **Framework** | Nuxt 3 (Vue 3 Composition API) |
| **Graph Library** | [@vue-flow/core](https://vueflow.dev/) + additional components |
| **Styling** | Tailwind CSS 4 + Headless UI + Custom CSS vars |
| **State** | Pinia (with persistence) |
| **Icons** | Custom SVG sprite system |
| **Rendering** | Shiki (syntax highlighting), Mermaid.js (diagrams), KaTeX (math), Marked (Markdown) + Web Worker |
| **UI Primitives** | Headless UI, Motion/VueUse |
| **API** | Custom `useAPI` composable (token refresh, error handling) |
| **Other** | TypeScript, ESLint, Prettier, Vite |

## Project Structure

```plaintext
ui/
├── app/                    # Main app source
│   ├── assets/             # Static assets
│   │   ├── css/main.css    # Global styles (Tailwind + custom theme)
│   │   ├── fonts/          # Custom fonts (Outfit Variable)
│   │   └── worker/         # Web Workers (Marked renderer)
│   ├── components/         # Vue components (auto-imported)
│   │   ├── ui/             # Reusable UI (chat, graph nodes, utils)
│   │   └── ...             # Page-specific
│   ├── composables/        # Logic (API, chat gen, graph actions, etc.)
│   ├── layouts/            # Layouts (blank, canvas)
│   ├── middleware/         # Auth middleware
│   ├── pages/              # Routes (graph/[id], index, settings)
│   ├── plugins/            # Runtime plugins (Mermaid, Marked worker)
│   ├── stores/             # Pinia stores (chat, canvasSave, stream, etc.)
│   └── types/              # TypeScript definitions
├── public/                 # Static public files (icons, favicons)
├── nuxt.config.ts          # Nuxt config (modules, Tailwind, etc.)
├── package.json            # Dependencies & scripts
└── tailwind.config.js      # Tailwind config (plugins, theme)
```

## Quick Start

### Prerequisites

- Node.js **18+** (pnpm recommended)
- Backend API running (see main README)

### Installation

```bash
cd ui
pnpm install
```

### Development Commands

```bash
# Development server (localhost:3000)
pnpm dev

# Build for production
pnpm build

# Preview production build
pnpm preview

# Lint & format
pnpm lint
pnpm lint:fix
```

## Core Concepts

### Graph Canvas

- **Vue Flow Instance**: `main-graph-${graphId}` (per-graph isolation).
- **Nodes**: Custom templates (`#node-{type}` slots) with resizers, handles, drag zones.
- **Edges**: Custom `edge-custom` with hover delete.
- **Drag & Drop**: Composables handle block dragging, auto-connections, overlaps.
- **Execution**: Visual plans, streaming animations.

### Chat Integration

- **Dual Mode**: Graph ↔ Chat sync via stores/events.
- **Rich Rendering**: Markdown → HTML via Marked worker (Shiki, KaTeX, Mermaid).
- **Streaming**: WebSocket chunks → real-time UI updates.
- **Editing**: Inline editable user messages with regeneration.

### Styling & Theming

- **Tailwind + CSS Vars**: 20+ custom colors (`--color-ember-glow`, etc.).
- **Themes**: `theme-standard/light/dark/oled` classes.
- **Fonts**: Outfit Variable (variable font for smooth weights).

### API Integration

- **`useAPI`**: Auto token refresh (401 retry), error toasts.
- **WebSocket**: Singleton with reconnect logic (`useWebSocket`).
- **File Uploads**: FormData blobs, drag-drop.

### State Management

| Store | Purpose |
|-------|---------|
| `chat` | Sessions per node, upcoming data |
| `canvasSave` | Auto-save cron, dirty state |
| `stream` | Streaming callbacks, sessions |
| `model` | Model list, filtering/sorting |
| `settings` | Global UI/config state |
| `sidebarCanvas` | Left/right sidebar toggles |

## Components Overview

| Path | Description |
|------|-------------|
| `ui/chat/*` | Chat UI (attachments, markdown, footers, utils) |
| `ui/graph/*` | Canvas (nodes, edges, execution plan, sidebar) |
| `ui/models/*` | Model selectors (virtualized, pinned, exacto) |
| `ui/settings/*` | Settings panels (account, blocks, tools) |
| `ui/toast/*` | Toast notifications |
| `ui/utils/*` | Reusable (icons, fullscreen, profile pic) |

**Key Patterns**:

- `<script setup lang="ts">` everywhere.
- `defineProps<>()` + `defineEmits<>()`.
- Composables over mixins.

## Composables Overview

| Name | Purpose |
|------|---------|
| `useAPI` | API calls + auth refresh |
| `useBlocks` | Node definitions (computed) |
| `useChatGenerator` | Generate/regenerate logic |
| `useChatScroll` | Auto-scroll chat |
| `useEdgeCompatibility` | Connection validation |
| `useGraphActions` | Node/edge CRUD, groups |
| `useGraphChat` | Chat-graph sync |
| `useGraphDragAndDrop` | DnD blocks/handles |
| `useGraphEvents` | Event bus (singleton) |
| `useMarkdownProcessor` | Parse/render Markdown |
| `useMarkedWorker` | Off-thread Markdown |
| `useMermaid` | Render diagrams |
| `useMessage` | Extract text/files |
| `useNodeRegistry` | Stream callbacks |

## Custom Tools

### Marked Web Worker

- `~/assets/worker/marked.worker.ts`: Shiki + KaTeX + Mermaid renderer.
- Off-main-thread for perf; singleton via `useMarkedWorker()`.

### Mermaid Rendering

- Plugin auto-inits Mermaid.
- Composables enhance blocks (fullscreen, copy).

## Building & Deployment

```bash
# Production build
pnpm build
```

**Env Vars**:

- `NUXT_PUBLIC_API_BASE_URL`: Backend URL.
- `NUXT_PUBLIC_IS_OAUTH_DISABLED`: Disable OAuth.

**Docker**: See root README for full-stack deploy.
