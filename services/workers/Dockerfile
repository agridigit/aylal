FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY services/workers/pyproject.toml ./
RUN pip install --no-cache-dir ".[dev]"
COPY services/workers/ ./
# Rendering code shared with the API (single source: services/api/app/operations); the worker image does not embed `app`.
COPY services/api/app/operations/export_job.py ./export_job.py
COPY services/api/app/operations/fonts/ ./fonts/
# F3 (single source: services/api): the shared visibility predicate, the gateways and the pure domain rules; the image does not embed `app`.
COPY services/api/app/monitoring/access_sql.py ./access_sql.py
COPY services/api/app/monitoring/gateways.py ./gateways.py
COPY services/api/app/domain/alert_rules.py services/api/app/domain/weather_thresholds.py services/api/app/domain/parcel_status.py \
     services/api/app/domain/notification_schedule.py services/api/app/domain/anomaly.py services/api/app/domain/imagery_reliability.py ./
CMD ["arq", "worker.WorkerSettings"]
