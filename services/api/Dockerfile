FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY services/api/pyproject.toml ./
RUN pip install --no-cache-dir . tzdata==2025.2
COPY services/api/ ./

FROM base AS test
RUN pip install --no-cache-dir ".[dev]"

FROM base AS runtime
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
