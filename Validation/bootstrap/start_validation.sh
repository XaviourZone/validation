#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export VALIDATION_HOME="$PROJECT_ROOT"
log(){ printf '[VALIDATION] %s\n' "$*"; }
if [[ "$(uname -s)" != "Linux" || "$(uname -m)" != "x86_64" ]]; then echo "[ERROR] Offline bootstrap supports Linux x86_64 only." >&2; exit 1; fi
log "Starting offline environment bootstrap..."
"$PROJECT_ROOT/Validation/bootstrap/check_environment.sh"
"$PROJECT_ROOT/Validation/bootstrap/install_python.sh"
"$PROJECT_ROOT/Validation/bootstrap/install_dependencies.sh"
PYTHON="$PROJECT_ROOT/.venv/bin/python"
mkdir -p "$PROJECT_ROOT/Validation/Data_Router/logs" "$PROJECT_ROOT/Validation/Data_Parser/logs" "$PROJECT_ROOT/Validation/Data_Forwarder/logs" "$PROJECT_ROOT/Validation/Web_Console/logs"
log "Validating Data Router configuration..."
"$PYTHON" -m Validation.Data_Router.app.main --validate-config
log "Starting Data Router..."
"$PYTHON" -m Validation.Data_Router.app.main > "$PROJECT_ROOT/Validation/Data_Router/logs/router-console.log" 2>&1 &
ROUTER_PID=$!
PARSER_PID=""; FORWARDER_PID=""; CONSOLE_PID=""
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
"$PYTHON" -m Validation.Data_Parser.app.main > "$PROJECT_ROOT/Validation/Data_Parser/logs/parser-console.log" 2>&1 &
PARSER_PID=$!
log "Starting Data Forwarder..."
"$PYTHON" -m Validation.Data_Forwarder.app.main > "$PROJECT_ROOT/Validation/Data_Forwarder/logs/forwarder-console.log" 2>&1 &
FORWARDER_PID=$!
log "Starting Web Console..."
"$PYTHON" -m Validation.Web_Console.app.main > "$PROJECT_ROOT/Validation/Web_Console/logs/console-console.log" 2>&1 &
CONSOLE_PID=$!
log "Validation services started."
log "Press Ctrl+C to stop all Validation services."
wait
