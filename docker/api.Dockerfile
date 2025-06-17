FROM python:3.11-slim

WORKDIR /app

COPY ./api/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY ./api/app .

ARG API_PORT
ENV API_PORT=${API_PORT}

EXPOSE ${API_PORT}

CMD uvicorn main:app --host 0.0.0.0 --port ${API_PORT}
