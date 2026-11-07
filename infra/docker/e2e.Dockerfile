FROM eclipse-temurin:17-jdk
RUN apt-get update && apt-get install -y --no-install-recommends curl unzip ca-certificates adb socat \
    && rm -rf /var/lib/apt/lists/*
# Maestro is fetched at build time only, from MAESTRO_URL (set by the Makefile, pinned there);
# it is never a runtime default. Build fails loudly if unset.
ARG MAESTRO_URL
RUN test -n "$MAESTRO_URL" || { echo "MAESTRO_URL is required"; exit 1; } \
    && curl -fsSL "$MAESTRO_URL" -o /tmp/maestro.zip && unzip -q /tmp/maestro.zip -d /root && rm /tmp/maestro.zip
ENV PATH="/root/maestro/bin:${PATH}" \
    MAESTRO_CLI_NO_ANALYTICS=1 \
    MAESTRO_CLI_ANALYSIS_NOTIFICATION_DISABLED=true
RUN printf '#!/bin/sh\nexec bash /repo/scripts/in-container/e2e-run.sh "$@"\n' > /usr/local/bin/e2e-run && chmod +x /usr/local/bin/e2e-run
WORKDIR /repo
CMD ["maestro", "--version"]
