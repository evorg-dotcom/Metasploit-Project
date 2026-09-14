#!/usr/bin/env bash
#
# 07-loot-collect.sh
# Pulls everything Metasploit has stashed in its loot table for the
# current workspace and copies it into ./loot/<workspace>/ with a
# manifest, so it's easy to grab later for the report without digging
# through ~/.msf4/loot.
#
# Usage: ./07-loot-collect.sh [workspace]

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source lib/common.sh

WS_NAME="${1:-$WORKSPACE}"
DEST="${LOOT_DIR}/${WS_NAME}"
mkdir -p "$DEST"

require_cmd msfconsole

MANIFEST="${DEST}/manifest.txt"

log_info "Collecting loot for workspace '${WS_NAME}' -> ${DEST}"
msfconsole -q -x "workspace ${WS_NAME}; loot; exit" | tee "$MANIFEST"

# loot entries print a path column - grab anything under ~/.msf4/loot and copy it over
MSF_LOOT_HOME="${HOME}/.msf4/loot"
if [[ -d "$MSF_LOOT_HOME" ]]; then
    COUNT=0
    while IFS= read -r path; do
        [[ -f "$path" ]] || continue
        cp "$path" "$DEST/" 2>/dev/null && COUNT=$((COUNT + 1))
    done < <(grep -oE "${MSF_LOOT_HOME}[^ ]+" "$MANIFEST" 2>/dev/null || true)
    log_info "Copied ${COUNT} loot file(s) into ${DEST}"
else
    log_warn "No ${MSF_LOOT_HOME} directory found, nothing to copy - only the manifest was saved"
fi
