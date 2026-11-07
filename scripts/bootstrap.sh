#!/usr/bin/env bash
# AYLAL - one-time setup. Host needs only docker, make and git; every other tool runs in a container.
set -euo pipefail
need() { command -v "$1" >/dev/null || { echo "manquant : $1 - $2"; exit 1; }; }
need git    "https://git-scm.com"
need docker "https://docs.docker.com/get-docker/"

[[ -d .git ]] || git init -q -b main
[[ -f .env ]] || cp .env.example .env
grep -q '^.aylal/' .gitignore 2>/dev/null || printf '.aylal/\n.env\nnode_modules/\n__pycache__/\n' >> .gitignore

# Spec Kit runs in a container (uv image); files are handed back to the current user.
docker run --rm -v "$PWD":/work -w /work ghcr.io/astral-sh/uv:python3.13-bookworm sh -c \
  "apt-get update -qq && apt-get install -y -qq git >/dev/null \
   && uvx --from git+https://github.com/github/spec-kit.git specify init --here --force --ai claude --script sh \
   && chown -R $(id -u):$(id -g) /work"

docker pull minlag/mermaid-cli:latest >/dev/null
git add -A && git commit -qm "chore: bootstrap AYLAL (Spec Kit, agents, Docker, docs)" || true
echo "Pret. Lancez : make up puis make check"
