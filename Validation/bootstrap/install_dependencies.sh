#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$PROJECT_ROOT/runtime/python/bin/python3"
VENV="$PROJECT_ROOT/.venv"
PACKAGE_DIR="$PROJECT_ROOT/offline_packages"
if [[ ! -x "$PYTHON" ]]; then echo "[ERROR] Bundled Python is not installed." >&2; exit 1; fi
if [[ ! -d "$PACKAGE_DIR" ]]; then echo "[ERROR] Offline package directory not found: $PACKAGE_DIR" >&2; exit 1; fi
if [[ ! -x "$VENV/bin/python" ]]; then echo "[BOOTSTRAP] Creating Validation virtual environment..."; "$PYTHON" -m venv "$VENV"; else echo "[BOOTSTRAP] Validation virtual environment already exists."; fi
VPYTHON="$VENV/bin/python"
echo "[BOOTSTRAP] Checking/installing dependencies from local package cache..."
"$VPYTHON" -m pip install --no-index --find-links="$PACKAGE_DIR" -r "$PROJECT_ROOT/Validation/Data_Parser/requirements.txt" -r "$PROJECT_ROOT/Validation/Data_Router/requirements.txt" -r "$PROJECT_ROOT/Validation/Data_Forwarder/requirements.txt" -r "$PROJECT_ROOT/Validation/Web_Console/requirements.txt"
echo "[OK] Python dependencies are ready."
"$VPYTHON" -c 'import yaml; print("[OK] PyYAML", yaml.__version__)'
"$VPYTHON" -c 'import psutil; print("[OK] psutil", psutil.__version__)'
"$VPYTHON" -c 'import paramiko; print("[OK] Paramiko", paramiko.__version__)'
