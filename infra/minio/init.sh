#!/bin/sh
set -eu
mc alias set local "http://minio:9000" "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}"
mc mb --ignore-existing local/aylal
# Stay alive once done so that `docker compose up --wait` sees a healthy service (not an exited one).
touch /tmp/ready
exec sleep infinity
