#!/usr/bin/env bash
set -euo pipefail
INSTALL_PACKAGES="${INSTALL_PACKAGES:-1}"
DB_NAME="${DB_NAME:-validation}"
DB_USER="${DB_USER:-validation}"
DB_PASSWORD="${DB_PASSWORD:-CHANGE_ME}"
SQL_FILE="${SQL_FILE:-$(dirname "$0")/001_create_validation_db.sql}"
if [[ "$INSTALL_PACKAGES" == "1" ]]; then sudo apt update; sudo apt install -y postgresql postgresql-client; fi
sudo systemctl enable postgresql
sudo systemctl start postgresql
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1 || sudo -u postgres psql -c "CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASSWORD}'"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1 || sudo -u postgres createdb -O "${DB_USER}" "${DB_NAME}"
sudo -u postgres psql -d "${DB_NAME}" -f "${SQL_FILE}"
echo "Validation PostgreSQL database ready: ${DB_NAME} / ${DB_USER}"
