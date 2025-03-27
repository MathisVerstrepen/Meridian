# Meridian UI

## File Structure

```bash
ui/
├── app.vue                  # Main app component
├── nuxt.config.ts           # Nuxt configuration
├── .env                     # Environment variables
├── public/
│   ├── favicon.ico
│   └── robots.txt
├── assets/
│   ├── styles/
│   │   ├── main.scss        # Global styles
│   │   ├── variables.scss   # SCSS variables
│   │   └── graph.scss       # Graph-specific styles
│   └── images/              # Static images
├── components/
│   ├── ui/
│   │   ├── Graph/
│   │   │   ├── GraphCanvas.vue   # Main graph visualization
│   │   │   ├── GraphNode.vue     # Individual node component
│   │   │   └── GraphEdge.vue     # Edge/connection component
│   │   ├── Chat/
│   │   │   ├── ChatWindow.vue    # Main chat interface
│   │   │   ├── MessageBubble.vue # Individual message component
│   │   │   └── InputPanel.vue    # Input with actions
│   │   └── common/
│   │       ├── AppButton.vue
│   │       └── AppSpinner.vue
│   └── layouts/
│       └── default.vue      # Main layout
├── composables/
│   ├── useChat.ts           # Chat logic
│   ├── useGraph.ts          # Graph interactions
│   ├── useLLM.ts            # LLM API calls
│   └── useWebSocket.ts      # Real-time communication
├── pages/
│   ├── index.vue            # Chat interface
│   ├── graph-explorer.vue   # Full graph visualization
│   ├── settings.vue         # User settings
├── plugins/
│   ├── graph-visualizer.client.ts  # Graph lib initialization
│   └── vue-query.client.ts         # API query client
├── server/
│   ├── api/
│   │   └── proxy.ts        # API proxy for sensitive calls
│   └── middleware/         # Server middleware
├── stores/
│   ├── useChatStore.ts     # Chat state (Pinia)
│   ├── useGraphStore.ts    # Graph state
├── types/
│   ├── chat.d.ts           # Type definitions
│   ├── graph.d.ts
│   └── llm.d.ts
├── utils/
│   ├── api.ts              # API client
│   ├── graphHelpers.ts     # Graph calculations
│   ├── validation.ts       # Input validation
│   └── websocket.ts        # WS connection handler
├── tests/
│   ├── unit/
│   │   ├── composables/
│   │   └── components/
│   └── e2e/
├── .gitignore
└── package.json
```