# Rendu Mermaid (SVG + PNG) hors ligne : Chromium système + mermaid-cli épinglés, aucun service tiers.
FROM node:22.12.0-bookworm-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends chromium fonts-liberation \
 && rm -rf /var/lib/apt/lists/*
ENV PUPPETEER_SKIP_DOWNLOAD=true PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium
RUN npm install -g @mermaid-js/mermaid-cli@11.4.2 \
 && printf '{"executablePath":"/usr/bin/chromium","args":["--no-sandbox","--disable-gpu"]}\n' > /etc/puppeteer.json
WORKDIR /data
ENTRYPOINT ["mmdc", "-p", "/etc/puppeteer.json"]
