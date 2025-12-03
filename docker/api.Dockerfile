# ---- Stage 1: Build Environment ----
FROM python:3.11-slim AS builder

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

# Install build-time Python tools and Chrome.
RUN pip install --no-cache-dir gunicorn patchright \
    && patchright install chrome

WORKDIR /app

# Copy and install application requirements, leveraging Docker's layer cache.
COPY ./api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# ---- Stage 2: Production Environment ----
FROM python:3.11-slim

# Prevent python from writing pyc files and bufferring stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       git \
       openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user and group for security
RUN groupadd --system appuser || true && useradd --system -g appuser appuser

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv

# Set the PATH to include the virtual environment's binaries
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Create data directories needed by the application
RUN mkdir -p /app/data/user_files /app/data/cloned_repos

# Copy application code, ensuring it's owned by the non-root user
COPY --chown=appuser:appuser ./api/app .
COPY --chown=appuser:appuser ./api/alembic.ini .
COPY --chown=appuser:appuser ./api/migrations ./migrations

# Set the default port
ENV API_PORT=8000
EXPOSE 8000

# Use the shell form of CMD to allow environment variable substitution.
CMD gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:${API_PORT}