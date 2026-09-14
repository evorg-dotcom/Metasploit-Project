#!/usr/bin/env bash
#
# 02-import-scan.sh
# Imports an nmap XML file (or any format db_import understands - Nessus,
# Nexpose, etc) into the active Metasploit workspace so hosts/services
# show up in `hosts` / `services` inside msfconsole.
#
# Usage: ./02-import-scan.sh <scan-file.xml> [workspace]

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source lib/common.sh

if [[ $# -lt 1 ]]; then
    log_err "Usage: $0 <scan-file.xml> [workspace]"
    exit 1
fi

SCAN_FILE="$1"
WS_NAME="${2:-$WORKSPACE}"

if [[ ! -f "$SCAN_FILE" ]]; then
    log_err "File not found: $SCAN_FILE"
    exit 1
fi

require_cmd msfconsole

log_info "Importing $SCAN_FILE into workspace '$WS_NAME'"
msfconsole -q -x "workspace ${WS_NAME}; db_import ${SCAN_FILE}; hosts -c address,os_name,purpose; exit"

log_info "Import complete."
