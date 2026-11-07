FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY services/workers/pyproject.toml ./
RUN pip install --no-cache-dir ".[dev]"
COPY services/workers/ ./
CMD ["arq", "worker.WorkerSettings"]
