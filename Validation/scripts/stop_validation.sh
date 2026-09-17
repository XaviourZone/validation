#!/usr/bin/env bash
set -u

# Stop all Validation services cleanly on Ubuntu/systemd.
# Missing units are ignored so this is safe during staged installation.
SERVICES=(
  validation-web.service
  validation-pans-importer.service
  validation-forwarder.service
  validation-parser.service
  validation-router.service
)

for service in "${SERVICES[@]}"; do
  if systemctl list-unit-files --type=service --no-legend "$service" 2>/dev/null | grep -q "$service"; then
    sudo systemctl stop "$service" || true
  fi
done

printf 'Validation services stopped.\n'
