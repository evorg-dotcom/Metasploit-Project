#!/usr/bin/env bash
#
# 00-setup-workspace.sh
# Gets the Metasploit database going and creates/selects a workspace
# for the current engagement. Run this first, before anything else
# in this folder.
#
# Usage: ./00-setup-workspace.sh [workspace-name]

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source lib/common.sh

WS_NAME="${1:-$WORKSPACE}"

require_cmd msfconsole
require_cmd msfdb

log_info "Checking postgresql..."
if command -v systemctl >/dev/null 2>&1; then
    if ! systemctl is-active --quiet postgresql; then
        log_warn "postgresql isn't running, starting it"
        sudo systemctl start postgresql
    fi
else
    # non-systemd fallback (docker images, some VMs)
    service postgresql start >/dev/null 2>&1 || true
fi

log_info "Making sure msfdb is initialized..."
msfdb init >/dev/null 2>&1 || log_warn "msfdb init reported an issue, continuing anyway (it may already be set up)"

log_info "Creating/selecting workspace: $WS_NAME"
msfconsole -q -x "workspace -a ${WS_NAME}; workspace ${WS_NAME}; db_status; exit"

log_info "Done. Workspace '${WS_NAME}' is ready."
log_info "Tip: export MSF_WORKSPACE=${WS_NAME} so the other scripts default to it."
