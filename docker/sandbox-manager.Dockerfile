FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /service

COPY ./sandbox_manager/requirements.txt ./sandbox_manager/requirements.txt
RUN pip install --no-cache-dir -r ./sandbox_manager/requirements.txt

COPY ./sandbox_manager ./sandbox_manager

WORKDIR /service/sandbox_manager
ENV SANDBOX_MANAGER_PORT=5000
EXPOSE 5000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${SANDBOX_MANAGER_PORT}"]
