#!/usr/bin/env bash
# Generate a self-signed TLS certificate for an intranet-only deployment of
# the Reservation Management System (no public CA can issue a cert for a
# name that isn't publicly resolvable, which is expected here).
#
# For an organization with an internal CA, prefer issuing a proper
# internal-CA-signed certificate instead and skip this script; either way
# the resulting files must land at the paths referenced by deploy/apache.conf.
#
# Usage:
#   sudo ./deploy/generate_self_signed_cert.sh [common-name] [days]
set -euo pipefail

COMMON_NAME="${1:-reservation-system.internal}"
DAYS="${2:-825}"
CERT_DIR="/etc/ssl/reservation-system"

if [ "$(id -u)" -ne 0 ]; then
  echo "This script must be run as root (sudo), so certs land in ${CERT_DIR} with correct permissions." >&2
  exit 1
fi

mkdir -p "${CERT_DIR}"
chmod 750 "${CERT_DIR}"

echo "[cert] Generating a ${DAYS}-day self-signed certificate for CN=${COMMON_NAME}"
openssl req -x509 -nodes \
  -newkey rsa:2048 \
  -days "${DAYS}" \
  -keyout "${CERT_DIR}/server.key" \
  -out "${CERT_DIR}/server.crt" \
  -subj "/C=US/ST=Internal/L=Internal/O=Reservation System/CN=${COMMON_NAME}" \
  -addext "subjectAltName=DNS:${COMMON_NAME}"

chmod 600 "${CERT_DIR}/server.key"
chmod 644 "${CERT_DIR}/server.crt"

echo "[cert] Wrote ${CERT_DIR}/server.crt and ${CERT_DIR}/server.key"
echo "[cert] Distribute ${CERT_DIR}/server.crt to internal client machines' trust"
echo "[cert] stores (or accept the one-time browser warning) since it is self-signed."
