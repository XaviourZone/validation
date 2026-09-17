#!/usr/bin/env bash
set -euo pipefail

VALIDATION_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$VALIDATION_ROOT/runtime/python/bin/python3"
VENV="$VALIDATION_ROOT/.venv"
PACKAGE_DIR="$VALIDATION_ROOT/offline_packages"

if [[ ! -x "$PYTHON" ]]; then
    echo "[ERROR] Bundled Python is not installed: $PYTHON" >&2
    exit 1
fi
if [[ ! -d "$PACKAGE_DIR" ]]; then
    echo "[ERROR] Offline package directory not found: $PACKAGE_DIR" >&2
    exit 1
fi
if [[ ! -x "$VENV/bin/python" ]]; then
    echo "[BOOTSTRAP] Creating Validation virtual environment..."
    "$PYTHON" -m venv "$VENV"
else
    echo "[BOOTSTRAP] Validation virtual environment already exists."
fi
VPYTHON="$VENV/bin/python"
echo "[BOOTSTRAP] Checking/installing dependencies from local package cache..."
"$VPYTHON" -m pip install --no-index --find-links="$PACKAGE_DIR" \
    -r "$VALIDATION_ROOT/Data_Parser/requirements.txt" \
    -r "$VALIDATION_ROOT/Data_Router/requirements.txt" \
    -r "$VALIDATION_ROOT/Data_Forwarder/requirements.txt" \
    -r "$VALIDATION_ROOT/Web_Console/requirements.txt"
echo "[OK] Python dependencies are ready."
"$VPYTHON" -c 'import yaml; print("[OK] PyYAML", yaml.__version__)'
"$VPYTHON" -c 'import psutil; print("[OK] psutil", psutil.__version__)'
"$VPYTHON" -c 'import paramiko; print("[OK] Paramiko", paramiko.__version__)'
