#!/usr/bin/env bash
# PreToolUse hook (Bash): blocks dangerous/remote git operations for AYLAL.
# Reads the hook JSON on stdin; exit 2 + stderr message = blocked, exit 0 = allowed.
set -u
input="$(cat)"
cmd="$(printf '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null)"
[ -z "$cmd" ] && exit 0

GUARD_CMD="$cmd" python3 - <<'PY'
import os, re, shlex, sys

cmd = os.environ["GUARD_CMD"]

def block(reason):
    sys.stderr.write(f"guard-git: bloqué — {reason}. AYLAL : git local uniquement.\n")
    sys.exit(2)

def tokenize(s):
    lex = shlex.shlex(s, posix=True, punctuation_chars=";&|()\n")
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    return list(lex)

try:
    tokens = tokenize(cmd)
except ValueError:
    # Unparseable: conservative regex fallback.
    for pat, why in [(r"\bgit\b[^\n;&|]*\bpush\b", "git push"),
                     (r"(^|[;&|\s])gh(\s|$)", "gh"),
                     (r"reset\s+--hard", "reset --hard"),
                     (r"filter-(branch|repo)", "réécriture d'historique")]:
        if re.search(pat, cmd):
            block(why)
    sys.exit(0)

SEP = set(";&|()\n") | {"&&", "||", ";;", "|&"}
segments, cur = [], []
for t in tokens:
    if t in SEP or set(t) <= set(";&|()\n"):
        if cur: segments.append(cur)
        cur = []
    else:
        cur.append(t)
if cur: segments.append(cur)

def is_env(t): return re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t) is not None
def base(t): return t.rsplit("/", 1)[-1]

for seg in segments:
    i = 0
    while i < len(seg) and (is_env(seg[i]) or seg[i] in ("sudo", "command", "exec", "env", "time", "nohup")):
        i += 1
    if i >= len(seg):
        continue
    prog = base(seg[i])
    if prog == "gh":
        block("commande gh")
    if prog != "git":
        continue
    # find subcommand (skip global options)
    j = i + 1
    while j < len(seg) and seg[j].startswith("-"):
        j += 2 if seg[j] in ("-C", "-c", "--git-dir", "--work-tree", "--namespace") else 1
    if j >= len(seg):
        continue
    sub, rest = seg[j], seg[j + 1:]
    if sub == "push":
        block("git push" + (" --force" if any(a in ("-f", "--force", "--force-with-lease") for a in rest) else ""))
    if sub in ("fetch", "pull"):
        block(f"git {sub}")
    if sub == "remote" and rest and rest[0] in ("add", "set-url"):
        block(f"git remote {rest[0]}")
    if sub == "reset" and "--hard" in rest:
        block("git reset --hard")
    if sub in ("filter-branch", "filter-repo"):
        block(f"git {sub} (réécriture d'historique)")
    if sub == "branch" and any(a in ("-D", "-d", "--delete") for a in rest) and "main" in rest:
        block("suppression de la branche main")
    if sub == "tag" and any(a in ("-d", "--delete") for a in rest) and any(re.match(r"^v\d", a) for a in rest):
        block("suppression d'une balise vX")
    if sub == "add":
        for a in rest:
            b = base(a)
            if b.startswith(".env") and b != ".env.example":
                block(f"git add {a} (secret)")
sys.exit(0)
PY
