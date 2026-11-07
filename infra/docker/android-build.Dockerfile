# Android release build (Expo prebuild + Gradle). linux/amd64 on purpose: Google's aapt2/NDK host
# binaries exist for linux-x86_64 only; Docker Desktop runs this image through Rosetta on Apple Silicon.
FROM --platform=linux/amd64 node:22-bookworm
ENV PNPM_HOME=/pnpm PATH=/pnpm:$PATH \
    ANDROID_HOME=/opt/android-sdk ANDROID_SDK_ROOT=/opt/android-sdk \
    GRADLE_USER_HOME=/cache/gradle
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-17-jdk-headless unzip curl rsync \
    && rm -rf /var/lib/apt/lists/*
RUN corepack enable && corepack prepare pnpm@9.15.0 --activate
# Command-line tools are fetched at build time only, from ANDROID_CMDLINE_URL (pinned in the Makefile).
ARG ANDROID_CMDLINE_URL
RUN test -n "$ANDROID_CMDLINE_URL" || { echo "ANDROID_CMDLINE_URL is required"; exit 1; } \
    && curl -fsSL "$ANDROID_CMDLINE_URL" -o /tmp/clt.zip \
    && mkdir -p /opt/android-cmdline/cmdline-tools && unzip -q /tmp/clt.zip -d /opt/android-cmdline/cmdline-tools \
    && mv /opt/android-cmdline/cmdline-tools/cmdline-tools /opt/android-cmdline/cmdline-tools/latest && rm /tmp/clt.zip
ENV PATH=/opt/android-cmdline/cmdline-tools/latest/bin:$PATH
WORKDIR /repo
CMD ["bash"]
