#!/usr/bin/env bash
#
# 01-recon-nmap.sh
# Kicks off the recon/scanning stage. Runs an nmap service scan against
# the given target(s) and writes XML output that 02-import-scan.sh can
# feed straight into the Metasploit db.
#
# Usage: ./01-recon-nmap.sh <target|CIDR> [extra nmap args...]
# Example: ./01-recon-nmap.sh 192.168.56.0/24
#          ./01-recon-nmap.sh 192.168.56.101 -p- -T4

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source lib/common.sh

if [[ $# -lt 1 ]]; then
    log_err "Usage: $0 <target|CIDR> [extra nmap args...]"
    exit 1
fi

TARGET="$1"
shift || true
EXTRA_ARGS=("$@")

require_cmd nmap

SCAN_DIR="${REPORT_DIR}/nmap"
mkdir -p "$SCAN_DIR"

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
SAFE_TARGET="$(echo "$TARGET" | tr '/:' '__')"
OUT_BASE="${SCAN_DIR}/${SAFE_TARGET}-${TIMESTAMP}"

log_info "Scanning $TARGET (this can take a while on -p-)..."
nmap -sV -sC -oA "$OUT_BASE" "${EXTRA_ARGS[@]:-}" "$TARGET"

log_info "Scan finished. XML written to ${OUT_BASE}.xml"
log_info "Next: ./02-import-scan.sh ${OUT_BASE}.xml"
