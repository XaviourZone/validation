#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$PROJECT_ROOT/runtime"
PYTHON_DIR="$RUNTIME_DIR/python"
PYTHON_VERSION="3.14.7"
ARCHIVE="$RUNTIME_DIR/cpython-3.14.7+20260814-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz"
EXPECTED_SHA256="cefba034445d2875408d1fd4d5700ae6731563aeb54dcb39fd8164ab5c457533"
if [[ -x "$PYTHON_DIR/bin/python3" ]]; then
    CURRENT="$("$PYTHON_DIR/bin/python3" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"
    if [[ "$CURRENT" == "$PYTHON_VERSION" ]]; then echo "[PYTHON] Python $CURRENT already installed. Skipping."; exit 0; fi
    echo "[PYTHON] Replacing bundled Python $CURRENT with $PYTHON_VERSION."
    rm -rf "$PYTHON_DIR"
fi
if [[ ! -f "$ARCHIVE" ]]; then echo "[ERROR] Bundled Python archive not found: $ARCHIVE" >&2; exit 1; fi
ACTUAL_SHA256="$(sha256sum "$ARCHIVE" | awk '{print $1}')"
if [[ "$ACTUAL_SHA256" != "$EXPECTED_SHA256" ]]; then echo "[ERROR] Python archive checksum mismatch." >&2; exit 1; fi
TMP_DIR="$(mktemp -d "$RUNTIME_DIR/python.extract.XXXXXX")"
trap 'rm -rf "$TMP_DIR"' EXIT
echo "[PYTHON] Extracting Python $PYTHON_VERSION..."
tar -xzf "$ARCHIVE" -C "$TMP_DIR"
if [[ ! -x "$TMP_DIR/python/bin/python3" ]]; then echo "[ERROR] Unexpected Python archive layout." >&2; exit 1; fi
mkdir -p "$RUNTIME_DIR"
mv "$TMP_DIR/python" "$PYTHON_DIR"
echo "[OK] Installed bundled Python: $("$PYTHON_DIR/bin/python3" --version 2>&1)"
