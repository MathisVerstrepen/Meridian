# Meridian API

## File Structure

````bash
api/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app initialization
│   ├── config.py            # Configuration settings
│   ├── database/
│   │   ├── __init__.py
│   │   ├── models.py        # Database models (Nodes, Edges, Conversations)
│   │   └── crud.py         # Database operations
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── chat.py         # Chat endpoints
│   │   ├── nodes.py        # Graph node management
│   │   ├── edges.py        # Graph edge management
│   │   └── sessions.py     # Chat session management
│   ├── schemas/            # Pydantic models
│   │   ├── __init__.py
│   │   ├── chat.py
│   │   ├── graph.py
│   │   └── base.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── llm_service.py  # OpenRouter API calls
│   │   ├── graph_service.py # Graph processing
│   │   └── cache.py        # Caching layer
│   ├── core/
│   │   ├── __init__.py
│   │   ├── security.py     # Authentication
│   │   ├── middleware.py
│   │   └── logging.py
│   └── utils/
│       ├── __init__.py
│       ├── helpers.py      # Utility functions
│       └── prompt_templates.py
├── tests/
│   ├── __init__.py
│   ├── test_chat.py
│   └── conftest.py
├── migrations/             # Database migration scripts (Alembic)
├── docker/
│   ├── Dockerfile
│   └── entrypoint.sh
├── docs/
│   └── api.md              # API documentation
├── requirements.txt        # Dependencies
├── docker-compose.yml      # DB & services setup
├── .env                    # Environment variables
└── .gitignore
````