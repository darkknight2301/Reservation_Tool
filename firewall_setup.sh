#!/usr/bin/env bash
# Configure the host firewall (ufw) so the Reservation Management System is
# reachable ONLY from your internal network - never from the public internet.
#
# This is the PRIMARY access control layer; deploy/nginx.conf's allow/deny
# directives are a secondary, defense-in-depth check on top of this.
#
# Usage:
#   sudo ./deploy/firewall_setup.sh 192.168.1.0/24 [10.0.0.0/8 ...]
#
# Pass one or more CIDR ranges for your internal network(s). If none are
# given, defaults to the three standard RFC1918 private ranges.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "This script must be run as root (sudo)." >&2
  exit 1
fi

if ! command -v ufw >/dev/null 2>&1; then
  echo "ufw is not installed. Install it first: apt-get install ufw" >&2
  exit 1
fi

CIDRS=("$@")
if [ "${#CIDRS[@]}" -eq 0 ]; then
  CIDRS=("10.0.0.0/8" "172.16.0.0/12" "192.168.0.0/16")
  echo "[firewall] No CIDR ranges supplied; defaulting to: ${CIDRS[*]}"
fi

echo "[firewall] Resetting ufw to a known-clean default-deny state"
ufw --force reset
ufw default deny incoming
ufw default allow outgoing

echo "[firewall] Allowing SSH (22/tcp) from the internal network only"
for cidr in "${CIDRS[@]}"; do
  ufw allow from "${cidr}" to any port 22 proto tcp
done

echo "[firewall] Allowing HTTPS (443/tcp) from the internal network only"
for cidr in "${CIDRS[@]}"; do
  ufw allow from "${cidr}" to any port 443 proto tcp
done

echo "[firewall] Allowing HTTP (80/tcp, redirects to HTTPS) from the internal network only"
for cidr in "${CIDRS[@]}"; do
  ufw allow from "${cidr}" to any port 80 proto tcp
done

echo "[firewall] Explicitly NOT opening any port to 0.0.0.0/0 (the public internet)."
echo "[firewall] Enabling ufw"
ufw --force enable

ufw status verbose
echo "[firewall] Done. Re-run this script any time your internal CIDR ranges change."
