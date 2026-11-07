#!/usr/bin/env bash
# AYLAL — installation initiale (à lancer une seule fois, à la racine du kit)
set -euo pipefail
need() { command -v "$1" >/dev/null || { echo "manquant : $1 — $2"; exit 1; }; }
need git    "https://git-scm.com"
need docker "https://docs.docker.com/get-docker/"
need node   "Node 20+ requis pour Claude Code"
need claude "npm install -g @anthropic-ai/claude-code"
command -v uv >/dev/null || { echo "installation de uv"; curl -LsSf https://astral.sh/uv/install.sh | sh; export PATH="$HOME/.local/bin:$PATH"; }

# 1. Spec Kit CLI
command -v specify >/dev/null || uv tool install specify-cli --from git+https://github.com/github/spec-kit.git
specify check || true

# 2. Dépôt git sur la branche main
[[ -d .git ]] || { git init -q -b main; }
[[ -f .env ]] || cp .env.example .env
grep -q '^.aylal/' .gitignore 2>/dev/null || printf '.aylal/\n.env\nnode_modules/\n__pycache__/\n' >> .gitignore

# 3. Spec Kit dans le dossier courant, pour Claude Code, scripts bash
specify init --here --force --ai claude --script sh

# 4. Image Mermaid pour les diagrammes
docker pull minlag/mermaid-cli:latest >/dev/null

git add -A && git commit -qm "chore: bootstrap AYLAL (Spec Kit, agents, Docker, docs)" || true
echo
echo "Prêt. Lancez :  make loop      (ou scripts/speckit-loop.sh F0 pour commencer par les fondations)"
