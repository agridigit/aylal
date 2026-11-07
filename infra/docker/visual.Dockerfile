FROM mcr.microsoft.com/playwright:v1.49.0-noble
ENV PNPM_HOME=/pnpm PATH=/pnpm:$PATH
RUN corepack enable && corepack prepare pnpm@9.15.0 --activate
WORKDIR /repo
CMD ["bash"]
