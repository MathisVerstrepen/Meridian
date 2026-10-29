# Node 24 supports the Mermaid 12 and provider runtime dependencies.
FROM node:24-trixie-slim AS node-runtime

# ---- Stage 1: Build Environment ----
FROM python:3.14-slim-trixie AS builder

# Prevent python from writing pyc files and bufferring stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install OS-level dependencies needed for building
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       openssh-client \
       git \
    && rm -rf /var/lib/apt/lists/*

# Create a virtual environment to isolate dependencies
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install the production process manager.
RUN pip install --no-cache-dir gunicorn

WORKDIR /app

# Copy and install application requirements, leveraging Docker's layer cache.
COPY ./api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- Stage 2: Production Environment ----
FROM python:3.14-slim-trixie

# Prevent python from writing pyc files and bufferring stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       git \
       openssh-client \
    && rm -rf /var/lib/apt/lists/*

COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=node-runtime /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

# Create a non-root user and group for security
RUN groupadd --system appuser || true && useradd --system --create-home --home-dir /home/appuser -g appuser appuser

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv

# Set the PATH to include the virtual environment's binaries
ENV PATH="/opt/venv/bin:$PATH"
ENV HOME=/home/appuser

WORKDIR /app

# Create data directories needed by the application
RUN mkdir -p /app/data/user_files /app/data/cloned_repos /app/ui/shared/mermaid /app/gemini_cli_runtime /app/openai_codex_runtime \
    && chown -R appuser:appuser /app/data

# Install the Mermaid runtime used by backend validation.
COPY ./ui/shared/mermaid/package.json /app/ui/shared/mermaid/package.json
COPY ./ui/shared/mermaid/package-lock.json /app/ui/shared/mermaid/package-lock.json
COPY ./ui/shared/mermaid/dompurify-shim /app/ui/shared/mermaid/dompurify-shim
RUN cd /app/ui/shared/mermaid && npm ci --omit=dev --ignore-scripts

# Install the Gemini CLI bridge runtime used by backend inference.
COPY ./api/app/gemini_cli_runtime/package.json /app/gemini_cli_runtime/package.json
COPY ./api/app/gemini_cli_runtime/package-lock.json /app/gemini_cli_runtime/package-lock.json
RUN cd /app/gemini_cli_runtime && npm ci --omit=dev --ignore-scripts

# Install the OpenAI Codex runtime used by backend inference.
COPY ./api/app/openai_codex_runtime/package.json /app/openai_codex_runtime/package.json
COPY ./api/app/openai_codex_runtime/package-lock.json /app/openai_codex_runtime/package-lock.json
RUN cd /app/openai_codex_runtime && npm ci --omit=dev --ignore-scripts

# Copy application code, ensuring it's owned by the non-root user
COPY --chown=appuser:appuser ./api/app .
COPY --chown=appuser:appuser ./api/alembic.ini .
COPY --chown=appuser:appuser ./api/migrations ./migrations
COPY --chown=appuser:appuser ./api/scripts/cutover_agents.py ./scripts/cutover_agents.py
COPY --chown=appuser:appuser ./ui/shared/mermaid/runtime.mjs /app/ui/shared/mermaid/runtime.mjs
COPY --chown=appuser:appuser ./ui/shared/mermaid/validate.mjs /app/ui/shared/mermaid/validate.mjs
COPY --chown=appuser:appuser ./ui/shared/mermaid/runtime.smoke.mjs /app/ui/shared/mermaid/runtime.smoke.mjs
COPY --chown=appuser:appuser ./ui/shared/runtimeTypes.mjs /app/ui/shared/runtimeTypes.mjs

# Set the default port
ENV API_PORT=8000
ENV MERMAID_VALIDATOR_SCRIPT=/app/ui/shared/mermaid/validate.mjs
EXPOSE 8000

USER appuser

# Fail the image build if its Node runtime cannot load the production Gemini bridge.
RUN npm --prefix /app/gemini_cli_runtime run smoke:bridge-imports
RUN npm --prefix /app/ui/shared/mermaid run smoke:parse

CMD ["sh", "-c", "alembic upgrade head && exec gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:${API_PORT}"]
