FROM eclipse-temurin:17-jdk
RUN apt-get update && apt-get install -y --no-install-recommends curl unzip ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL "https://get.maestro.mobile.dev" | bash
ENV PATH="/root/.maestro/bin:${PATH}"
WORKDIR /repo
CMD ["maestro", "--version"]
