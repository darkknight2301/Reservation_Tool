#!/usr/bin/env bash
# Gracefully stop the Reservation Management System.
#
# Usage: ./deploy/shutdown.sh
#
# Prefers systemd if the unit is installed; otherwise sends a graceful
# TERM (via Gunicorn's own signal handling) to any running Gunicorn master
# process bound to this project's working directory.
set -euo pipefail

SERVICE_NAME="reservation-system"

if systemctl list-unit-files 2>/dev/null | grep -q "^${SERVICE_NAME}.service"; then
  echo "[shutdown] Stopping via systemd (${SERVICE_NAME})"
  sudo systemctl stop "${SERVICE_NAME}"
else
  echo "[shutdown] systemd unit not found; looking for a running Gunicorn master process"
  PID="$(pgrep -f "gunicorn -c deploy/gunicorn_conf.py app.main:app" -o || true)"
  if [ -z "${PID}" ]; then
    echo "[shutdown] No matching Gunicorn process found."
    exit 0
  fi
  echo "[shutdown] Sending graceful TERM to PID ${PID}"
  kill -TERM "${PID}"
fi

echo "[shutdown] Done."
