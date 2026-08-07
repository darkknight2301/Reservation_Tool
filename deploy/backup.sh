#!/usr/bin/env bash
# Backup the Reservation Management System database and logs/ directory.
#
# Usage: ./deploy/backup.sh [backup_dir]
#
# Reads DATABASE_URL from the environment, or from a .env file in the
# project root if present. Detects SQLite vs PostgreSQL automatically.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKUP_ROOT="${1:-${PROJECT_ROOT}/backups}"
TIMESTAMP="$(date -u +%Y%m%d-%H%M%S)"
WORK_DIR="$(mktemp -d)"

cleanup() { rm -rf "${WORK_DIR}"; }
trap cleanup EXIT

if [ -f "${PROJECT_ROOT}/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "${PROJECT_ROOT}/.env"
  set +a
fi

DATABASE_URL="${DATABASE_URL:-sqlite:///./reservation_system.db}"
mkdir -p "${BACKUP_ROOT}"

echo "[backup] Using DATABASE_URL=${DATABASE_URL}"

if [[ "${DATABASE_URL}" == sqlite:///* ]]; then
  DB_PATH="${DATABASE_URL#sqlite:///}"
  # Resolve relative paths against the project root.
  case "${DB_PATH}" in
    /*) ;;
    *) DB_PATH="${PROJECT_ROOT}/${DB_PATH}" ;;
  esac

  if [ ! -f "${DB_PATH}" ]; then
    echo "[backup] ERROR: SQLite database file not found at ${DB_PATH}" >&2
    exit 1
  fi

  echo "[backup] Backing up SQLite database at ${DB_PATH} (safe online .backup)"
  sqlite3 "${DB_PATH}" ".backup '${WORK_DIR}/reservation_system.db'"

elif [[ "${DATABASE_URL}" == postgresql* ]]; then
  echo "[backup] Backing up PostgreSQL database via pg_dump"
  pg_dump --dbname="${DATABASE_URL}" --format=custom --file="${WORK_DIR}/reservation_system.pgdump"

else
  echo "[backup] ERROR: Unsupported DATABASE_URL scheme: ${DATABASE_URL}" >&2
  exit 1
fi

if [ -d "${PROJECT_ROOT}/logs" ]; then
  echo "[backup] Copying logs/ directory"
  cp -r "${PROJECT_ROOT}/logs" "${WORK_DIR}/logs"
fi

ARCHIVE_PATH="${BACKUP_ROOT}/reservation-system-backup-${TIMESTAMP}.tar.gz"
tar -czf "${ARCHIVE_PATH}" -C "${WORK_DIR}" .
echo "[backup] Created ${ARCHIVE_PATH} ($(du -h "${ARCHIVE_PATH}" | cut -f1))"
