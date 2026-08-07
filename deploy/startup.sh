#!/usr/bin/env bash
# Start the Reservation Management System.
#
# Usage: ./deploy/startup.sh
#
# Prefers the systemd service if installed; otherwise runs Gunicorn directly
# in the foreground (useful for a bare VM without systemd, or local testing
# of the production Gunicorn config).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SERVICE_NAME="reservation-system"

if systemctl list-unit-files 2>/dev/null | grep -q "^${SERVICE_NAME}.service"; then
  echo "[startup] Starting via systemd (${SERVICE_NAME})"
  sudo systemctl start "${SERVICE_NAME}"
  sudo systemctl status "${SERVICE_NAME}" --no-pager
else
  echo "[startup] systemd unit not found; starting Gunicorn directly"
  cd "${PROJECT_ROOT}"
  if [ -d "venv" ]; then
    # shellcheck disable=SC1091
    source venv/bin/activate
  fi
  exec gunicorn -c deploy/gunicorn_conf.py app.main:app
fi
