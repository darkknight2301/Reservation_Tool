#!/usr/bin/env bash
# Restore the Reservation Management System database and logs/ directory
# from an archive produced by deploy/backup.sh.
#
# Usage: ./deploy/restore.sh <path-to-backup.tar.gz>
#
# WARNING: this overwrites the current database and logs/ directory.
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <path-to-backup.tar.gz>" >&2
  exit 1
fi

ARCHIVE_PATH="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
WORK_DIR="$(mktemp -d)"

cleanup() { rm -rf "${WORK_DIR}"; }
trap cleanup EXIT

if [ ! -f "${ARCHIVE_PATH}" ]; then
  echo "[restore] ERROR: archive not found: ${ARCHIVE_PATH}" >&2
  exit 1
fi

if [ -f "${PROJECT_ROOT}/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "${PROJECT_ROOT}/.env"
  set +a
fi

DATABASE_URL="${DATABASE_URL:-sqlite:///./reservation_system.db}"

read -r -p "This will OVERWRITE the current database and logs/ directory. Continue? [y/N] " CONFIRM
if [[ ! "${CONFIRM}" =~ ^[Yy]$ ]]; then
  echo "[restore] Aborted."
  exit 0
fi

echo "[restore] Extracting ${ARCHIVE_PATH}"
tar -xzf "${ARCHIVE_PATH}" -C "${WORK_DIR}"

SERVICE_NAME="reservation-system"
if systemctl is-active --quiet "${SERVICE_NAME}" 2>/dev/null; then
  echo "[restore] Stopping ${SERVICE_NAME}"
  sudo systemctl stop "${SERVICE_NAME}"
  RESTART_SERVICE=1
else
  RESTART_SERVICE=0
fi

if [[ "${DATABASE_URL}" == sqlite:///* ]]; then
  DB_PATH="${DATABASE_URL#sqlite:///}"
  case "${DB_PATH}" in
    /*) ;;
    *) DB_PATH="${PROJECT_ROOT}/${DB_PATH}" ;;
  esac

  if [ ! -f "${WORK_DIR}/reservation_system.db" ]; then
    echo "[restore] ERROR: archive does not contain reservation_system.db" >&2
    exit 1
  fi

  echo "[restore] Restoring SQLite database to ${DB_PATH}"
  cp "${WORK_DIR}/reservation_system.db" "${DB_PATH}"

elif [[ "${DATABASE_URL}" == postgresql* ]]; then
  if [ ! -f "${WORK_DIR}/reservation_system.pgdump" ]; then
    echo "[restore] ERROR: archive does not contain reservation_system.pgdump" >&2
    exit 1
  fi

  echo "[restore] Restoring PostgreSQL database via pg_restore (--clean)"
  pg_restore --dbname="${DATABASE_URL}" --clean --if-exists "${WORK_DIR}/reservation_system.pgdump"

else
  echo "[restore] ERROR: Unsupported DATABASE_URL scheme: ${DATABASE_URL}" >&2
  exit 1
fi

if [ -d "${WORK_DIR}/logs" ]; then
  echo "[restore] Restoring logs/ directory"
  rm -rf "${PROJECT_ROOT}/logs"
  cp -r "${WORK_DIR}/logs" "${PROJECT_ROOT}/logs"
fi

if [ "${RESTART_SERVICE}" -eq 1 ]; then
  echo "[restore] Restarting ${SERVICE_NAME}"
  sudo systemctl start "${SERVICE_NAME}"
fi

echo "[restore] Done."
