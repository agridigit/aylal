FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY services/workers/pyproject.toml ./
RUN pip install --no-cache-dir ".[dev]"
COPY services/workers/ ./
# Rendering code shared with the API (single source: services/api/app/operations); the worker image does not embed `app`.
COPY services/api/app/operations/export_job.py ./export_job.py
COPY services/api/app/operations/fonts/ ./fonts/
CMD ["arq", "worker.WorkerSettings"]
