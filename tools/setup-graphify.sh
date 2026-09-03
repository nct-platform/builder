#!/usr/bin/env bash
# setup-graphify.sh — install the graphify knowledge-graph skill for the builder's COMPREHENSION layer.
#
# WHY: verifying a platform mechanism (how locale resolves, how a plugin reads its config, which DTO a field
# maps to) across ~30 cross-linked docs is grep-heavy. graphify (github.com/Graphify-Labs/
# graphify, Apache-2.0) turns the codebase + docs into a queryable knowledge graph (tree-sitter AST, no vectors)
# so the builder AI can TRAVERSE relationships instead of grepping. See doc 26 §7. It is a READ/UNDERSTAND aid —
# it does NOT build/validate/import a .mrjun; that stays the Workflow tool + plan.json.
#
# This script does the INSTALL steps only (so nobody installs by hand). Building the graphs is a one-line
# `/graphify` SKILL call inside Claude Code (it needs the assistant's model for the docs/PDF semantic pass) — see
# the "Next steps" printed at the end. Idempotent: safe to re-run to refresh after a platform/tooling upgrade.
set -euo pipefail

log()  { printf '\033[1;34m[graphify-setup]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[graphify-setup] WARN:\033[0m %s\n' "$*" >&2; }

PKG="graphifyy"   # PyPI package name (double-y); the CLI command is `graphify`

if command -v graphify >/dev/null 2>&1; then
  log "graphify already installed: $(command -v graphify)  ($(graphify --version 2>/dev/null || echo 'version n/a'))"
else
  log "installing $PKG ..."
  if command -v uv >/dev/null 2>&1; then
    uv tool install "$PKG" || uv tool upgrade "$PKG"
    uv tool update-shell 2>/dev/null || true
  elif command -v pipx >/dev/null 2>&1; then
    pipx install "$PKG" 2>/dev/null || pipx upgrade "$PKG"
    pipx ensurepath 2>/dev/null || true
  elif command -v python3 >/dev/null 2>&1; then
    warn "neither uv nor pipx found; falling back to 'python3 -m pip install --user $PKG' (isolated install via uv/pipx is preferred)."
    python3 -m pip install --user --upgrade "$PKG"
  else
    warn "no uv / pipx / python3 found — install one, then re-run this script."
    exit 1
  fi
fi

# Make the freshly-installed CLI reachable in THIS shell (uv/pipx put it under ~/.local/bin).
export PATH="$HOME/.local/bin:${PATH}"

if ! command -v graphify >/dev/null 2>&1; then
  warn "graphify installed but not on PATH yet. Open a new shell (or 'uv tool update-shell' / 'pipx ensurepath'), then re-run."
  exit 1
fi

log "registering the /graphify skill with Claude Code ..."
graphify install || warn "'graphify install' returned non-zero — the skill may already be registered; verify with /help in Claude Code."

log "done — graphify is installed and the /graphify skill is registered."
cat <<'EOF'

────────────────────────────────────────────────────────────────────────────
Next steps — build the two graphs (run INSIDE Claude Code; the docs pass uses the model):

  # 1) the builder docs (this folder's concept map) — run from doc/builder:
  /graphify .                       # or:  /graphify . --update   to refresh only changed files

  # 2) the platform codebase (mechanism verification / doc code-anchor re-checks):
  (maintainers only, needs a platform checkout — not part of this library:)
  # /graphify <path-to-platform-checkout>

Each writes graphify-out/{graph.html, GRAPH_REPORT.md, graph.json}. Then query instead of grepping, e.g.:

  /graphify query "how is the UI locale resolved when a localizedMap key is missing?"
  /graphify path "SiteMapPage" "ContentDbServiceImpl"
  /graphify explain "quicklink localizedMap"

Pin the installed graphify version next to the platform build pin (doc 23 §3); re-run this script to upgrade.
────────────────────────────────────────────────────────────────────────────
EOF
