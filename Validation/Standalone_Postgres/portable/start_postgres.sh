#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
PGROOT="$ROOT/linux-x64"
DATA="$ROOT/data"
if [[ ! -f "$DATA/PG_VERSION" ]]; then "$PGROOT/bin/initdb" -D "$DATA" -U validation -A scram-sha-256 -E UTF8; fi
"$PGROOT/bin/pg_ctl" -D "$DATA" -l "$ROOT/postgres.log" -o "-p 5432" start
