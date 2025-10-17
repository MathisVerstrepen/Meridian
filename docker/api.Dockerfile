FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends openssh-client git \
    && rm -rf /var/lib/apt/lists/*

COPY ./api/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

RUN patchright install chrome

COPY ./api/app .
COPY ./api/alembic.ini .
COPY ./api/migrations ./migrations

ENV API_PORT=8000

EXPOSE 8000

CMD uvicorn main:app --host 0.0.0.0 --port ${API_PORT}