#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$PROJECT_ROOT/runtime/python"
VENV_DIR="$PROJECT_ROOT/.venv"
log(){ printf '[VALIDATION] %s\n' "$*"; }
ok(){ printf '[OK] %s\n' "$*"; }
warn(){ printf '[WARN] %s\n' "$*"; }
log "Project root: $PROJECT_ROOT"
log "Host kernel: $(uname -srm)"
if [[ "$(uname -s)" != "Linux" ]]; then echo "[ERROR] Linux is required." >&2; exit 1; fi
ARCH="$(uname -m)"
if [[ "$ARCH" != "x86_64" ]]; then echo "[ERROR] Unsupported architecture: $ARCH. Expected x86_64." >&2; exit 1; fi
ok "Architecture: x86_64"
if command -v ldd >/dev/null 2>&1; then log "Host libc: $(ldd --version 2>&1 | head -n 1 || true)"; fi
if [[ -x "$RUNTIME_DIR/bin/python3" ]]; then ok "Bundled Python runtime found: $("$RUNTIME_DIR/bin/python3" --version 2>&1)"; else warn "Bundled Python runtime is not installed yet."; fi
if [[ -x "$VENV_DIR/bin/python" ]]; then ok "Validation virtual environment exists: $VENV_DIR"; else warn "Validation virtual environment does not exist yet."; fi
