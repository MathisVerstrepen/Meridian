# Meridian Configuration File

Meridian uses a `config.toml` file to manage its configuration settings. 
This file is structured into sections, each containing key-value pairs that define various aspects of the application, 
such as environment settings, UI configurations, API settings, database connections, and more.

### 1. `[general]`

This section contains general settings for the overall application environment.

*   `ENV`
    *   **Description**: Specifies the application's environment.
    *   **Example**: `prod`, `dev`.
    *   **Type**: String
*   `NAME`
    *   **Description**: The logical name of the project used as a prefix for docker containers names.
    *   **Example**: `meridian_prod`, `meridian_dev`.
    *   **Type**: String
*   `USERPASS`
    *   **Description**: A comma-separated list of `username:password` pairs. These credentials are used to create initial users in the system on API startup.
    *   **Example**: `admin:adminpwd,user1:user1pwd`.
    *   **Type**: String

### 2. `[ui]`

This section configures settings specific to the user interface application.

*   `NITRO_PORT`
    *   **Description**: The port on which the Nuxt.js Nitro server will listen and to which to docker will bind and expose.
    *   **Example**: `3000`.
    *   **Type**: Integer
*   `NUXT_PUBLIC_API_BASE_URL`
    *   **Description**: The base URL for the API backend that the Nuxt.js UI will use to make requests, accessible publicly (e.g., from the browser).
    *   **Example**:
     `https://api.example.com`
    *   **Type**: String
*   `NUXT_API_INTERNAL_BASE_URL`
    *   **Description**: The internal base URL for the API backend, used for server-side communication.
    *   **Example**:
     `http://api:8000`
    *   **Type**: String
*   `NUXT_SESSION_PASSWORD`
    *   **Description**: A secret key used by Nuxt.js for session management.
    *   **Generate**:
     `python -c "import os; print(os.urandom(32).hex())"`
    *   **Type**: String (Hexadecimal)
*   `NUXT_PUBLIC_IS_OAUTH_DISABLED`
    *   **Description**: A flag to globally disable OAuth authentication options in the UI.
    *   **Example**: `true`, `false`.
    *   **Type**: Boolean (String representation)
*   `NUXT_OAUTH_GITHUB_CLIENT_ID`
    *   **Description**: The client ID for GitHub OAuth integration.
    *   **Type**: String
    *   **Generate**: Go to your Github account settings, then to "Developer settings" > "OAuth Apps" and create a new OAuth application to get the client ID and secret.
*   `NUXT_OAUTH_GITHUB_CLIENT_SECRET`
    *   **Description**: The client secret for GitHub OAuth integration.
    *   **Type**: String
*   `NUXT_OAUTH_GOOGLE_CLIENT_ID`
    *   **Description**: The client ID for Google OAuth integration.
    *   **Type**: String
    *   **Generate**: Go to the Google Cloud Console, create a new project, and set up OAuth 2.0 credentials to get the client ID and secret.
*   `NUXT_OAUTH_GOOGLE_CLIENT_SECRET`
    *   **Description**: The client secret for Google OAuth integration.
    *   **Type**: String

### 3. `[api]`

This section contains configurations for the backend API server.

*   `API_PORT`
    *   **Description**: The port on which the API server will listen and to which Docker will bind and expose.
    *   **Example**: `8000`.
    *   **Type**: Integer
*   `PYTHONUNBUFFERED`
    *   **Description**: If set to `1`, forces Python's stdout and stderr streams to be unbuffered. Useful for real-time logging in containerized environments. Recommended to set to `1` in production for logging in docker containers.
    *   **Example**: `1`.
    *   **Type**: Integer
*   `ALLOW_CORS_ORIGINS`
    *   **Description**: A comma-separated list of origins that are allowed to make cross-origin requests to the API. Use `*` for all origins (not recommended for production).
    *   **Example**:
     `https://meridian.example.com`
    *   **Type**: String
*   `MASTER_OPEN_ROUTER_API_KEY`
    *   **Description**: The API key for the OpenRouter service. This is ONLY used to get the list of available models from OpenRouter. No cost will be incurred by using this key. This key is required for the backend to start properly.
    *   **Generate**: Go to the [OpenRouter website](https://openrouter.ai/) and create an account to get your API key.
    *   **Type**: String
*   `DATABASE_ECHO`
    *   **Description**: If `true`, the database ORM (SQLModel) will echo all SQL statements to stdout, useful for debugging.
    *   **Example**: `false`.
    *   **Type**: Boolean (String representation)
*   `BACKEND_SECRET`
    *   **Description**: A general-purpose secret key used by the backend for various cryptographic operations (e.g., signing cookies, data encryption).
    *   **Generate**:
     `python -c "import os; print(os.urandom(32).hex())"`
    *   **Type**: String (Hexadecimal)
*   `JWT_SECRET_KEY`
    *   **Description**: The secret key used for signing JSON Web Tokens (JWTs).
    *   **Generate**:
     `python -c "import os; print(os.urandom(32).hex())"`
    *   **Type**: String (Hexadecimal)

### 4. `[database]`

This section configures the connection details for the PostgreSQL database.

*   `POSTGRES_DB`
    *   **Description**: The name of the PostgreSQL database to connect to.
    *   **Example**: `postgres`.
    *   **Type**: String
*   `POSTGRES_USER`
    *   **Description**: The username for connecting to the PostgreSQL database.
    *   **Example**: `postgres`.
    *   **Type**: String
*   `POSTGRES_PASSWORD`
    *   **Description**: The password for the PostgreSQL database user.
    *   **Type**: String
*   `POSTGRES_HOST`
    *   **Description**: The hostname or IP address of the PostgreSQL database server.
    *   **Example**: `db` (for Docker Compose service) or `localhost` (for local development).
    *   **Type**: String
*   `POSTGRES_PORT`
    *   **Description**: The port number on which the PostgreSQL database server is listening and to which Docker will bind and expose.
    *   **Example**: `5432`.
    *   **Type**: Integer

### 5. `[neo4j]`

This section configures the connection details for the Neo4j graph database.

*   `NEO4J_USER`
    *   **Description**: The username for connecting to the Neo4j database.
    *   **Example**: `neo4j`.
    *   **Type**: String
*   `NEO4J_PASSWORD`
    *   **Description**: The password for the Neo4j database user.
    *   **Type**: String
*   `NEO4J_HOST`
    *   **Description**: The hostname or IP address of the Neo4j database server.
    *   **Example**: `neo4j` (for Docker Compose service) or `localhost` (for local development).
    *   **Type**: String
*   `NEO4J_BOLT_PORT`
    *   **Description**: The port number for the Neo4j Bolt protocol, used for direct client connections. When changing this, ensure that `NEO4J_BOLT_ADDRESS` is also updated accordingly. This port will be bound and exposed by Docker.
    *   **Example**: `1111`.
    *   **Type**: Integer
*   `NEO4J_BOLT_ADDRESS`
    *   **Description**: The address on which the Neo4j Bolt server will listen. Used for Neo4j internal configuration.
    *   **Example**:
     `0.0.0.0:1111`
    *   **Type**: String
*   `NEO4J_HTTP_PORT`
    *   **Description**: The port number for the Neo4j HTTP API, used for Neo4j web interface. When changing this, ensure that `NEO4J_HTTP_ADDRESS` is also updated accordingly. This port will be bound and exposed by Docker.
    *   **Example**: `2222`.
    *   **Type**: Integer
*   `NEO4J_HTTP_ADDRESS`
    *   **Description**: The address on which the Neo4j HTTP API server will listen. Used for Neo4j internal configuration.
    *   **Example**:
     `0.0.0.0:2222`
    *   **Type**: String

