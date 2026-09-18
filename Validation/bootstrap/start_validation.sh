#!/usr/bin/env bash
set -euo pipefail

VALIDATION_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$VALIDATION_ROOT/.." && pwd)"

export VALIDATION_HOME="$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"

log(){ printf '[VALIDATION] %s\n' "$*"; }

if [[ "$(uname -s)" != "Linux" || "$(uname -m)" != "x86_64" ]]; then
    echo "[ERROR] Offline bootstrap supports Linux x86_64 only." >&2
    exit 1
fi

log "Starting offline environment bootstrap..."
bash "$VALIDATION_ROOT/bootstrap/check_environment.sh"
bash "$VALIDATION_ROOT/bootstrap/install_python.sh"
bash "$VALIDATION_ROOT/bootstrap/install_dependencies.sh"

PYTHON="$VALIDATION_ROOT/.venv/bin/python"

mkdir -p "$VALIDATION_ROOT/Data_Router/logs" "$VALIDATION_ROOT/Data_Parser/logs" "$VALIDATION_ROOT/Data_Forwarder/logs" "$VALIDATION_ROOT/Web_Console/logs"

log "Validating Data Router configuration..."
"$PYTHON" -m Validation.Data_Router.app.main --validate-config

log "Starting Data Router..."
"$PYTHON" -m Validation.Data_Router.app.main > "$VALIDATION_ROOT/Data_Router/logs/router-console.log" 2>&1 &
ROUTER_PID=$!
PARSER_PID=""
FORWARDER_PID=""
CONSOLE_PID=""
cleanup(){
    log "Stopping Validation services..."
    [[ -n "${ROUTER_PID:-}" ]] && kill "$ROUTER_PID" 2>/dev/null || true
    [[ -n "${PARSER_PID:-}" ]] && kill "$PARSER_PID" 2>/dev/null || true
    [[ -n "${FORWARDER_PID:-}" ]] && kill "$FORWARDER_PID" 2>/dev/null || true
    [[ -n "${CONSOLE_PID:-}" ]] && kill "$CONSOLE_PID" 2>/dev/null || true
}
trap cleanup INT TERM EXIT
sleep 2
log "Starting Data Parser..."
"$PYTHON" -m Validation.Data_Parser.app.main > "$VALIDATION_ROOT/Data_Parser/logs/parser-console.log" 2>&1 &
PARSER_PID=$!
log "Starting Data Forwarder..."
"$PYTHON" -m Validation.Data_Forwarder.app.main > "$VALIDATION_ROOT/Data_Forwarder/logs/forwarder-console.log" 2>&1 &
FORWARDER_PID=$!
log "Starting Web Console..."
"$PYTHON" -m Validation.Web_Console.app.main > "$VALIDATION_ROOT/Web_Console/logs/console-console.log" 2>&1 &
CONSOLE_PID=$!
log "Validation services started."
log "Press Ctrl+C to stop all Validation services."
wait
