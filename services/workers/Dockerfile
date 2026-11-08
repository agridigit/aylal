FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
# rasterio wheels link against libexpat
RUN apt-get update && apt-get install -y --no-install-recommends libexpat1 && rm -rf /var/lib/apt/lists/*
COPY services/workers/pyproject.toml ./
RUN pip install --no-cache-dir ".[dev]" tzdata==2025.2
COPY services/workers/ ./
# Rendering code shared with the API (single source: services/api/app/operations); the worker image does not embed `app`.
COPY services/api/app/operations/export_job.py ./export_job.py
COPY services/api/app/operations/fonts/ ./fonts/
# F3 (single source: services/api): the shared visibility predicate, the gateways and the pure domain rules; the image does not embed `app`.
COPY services/api/app/monitoring/access_sql.py ./access_sql.py
COPY services/api/app/monitoring/gateways.py ./gateways.py
COPY services/api/app/monitoring/imagery.py services/api/app/monitoring/zones.py services/api/app/monitoring/status_sources.py ./
COPY services/api/app/domain/alert_rules.py services/api/app/domain/weather_thresholds.py services/api/app/domain/parcel_status.py \
     services/api/app/domain/notification_schedule.py services/api/app/domain/anomaly.py services/api/app/domain/imagery_reliability.py services/api/app/domain/vigor.py ./
# F4 (single source: services/api): the clock, the pure irrigation rules, the plan engine and the worker view; the image does not embed `app`.
COPY services/api/app/domain/clock.py services/api/app/domain/irrigation_advice.py services/api/app/domain/water_balance.py \
     services/api/app/domain/advice_worker_view.py services/api/app/domain/application_rate.py services/api/app/domain/leaching.py \
     services/api/app/domain/rainfed_stress.py services/api/app/domain/irrigation_efficiency.py services/api/app/domain/irrigation_units.py \
     services/api/app/domain/et0.py services/api/app/domain/effective_rain.py services/api/app/domain/advice_confidence.py ./
COPY services/api/app/irrigation/worker_view.py services/api/app/irrigation/weather_input.py ./
COPY services/api/app/irrigation/engine.py ./irrigation_engine.py
CMD ["arq", "worker.WorkerSettings"]
