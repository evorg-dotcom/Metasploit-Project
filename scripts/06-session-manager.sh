#!/usr/bin/env bash
#
# 06-session-manager.sh
# Small helper for dealing with active Meterpreter/shell sessions
# without having to remember the exact msfconsole syntax each time.
#
# Usage: ./06-session-manager.sh <list|kill ID|kill-all|upgrade ID>

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source lib/common.sh

usage() {
    cat <<EOF
Usage: $0 <command> [args]

Commands:
  list              show active sessions
  kill <id>         kill a specific session
  kill-all          kill every active session
  upgrade <id>       upgrade a shell session to meterpreter (Windows only)
EOF
    exit 1
}

[[ $# -ge 1 ]] || usage
require_cmd msfconsole

CMD="$1"
shift || true

case "$CMD" in
    list)
        msfconsole -q -x "sessions -l; exit"
        ;;
    kill)
        [[ $# -ge 1 ]] || usage
        log_warn "Killing session $1"
        msfconsole -q -x "sessions -k $1; exit"
        ;;
    kill-all)
        log_warn "Killing ALL active sessions"
        msfconsole -q -x "sessions -K; exit"
        ;;
    upgrade)
        [[ $# -ge 1 ]] || usage
        log_info "Upgrading session $1 to meterpreter"
        msfconsole -q -x "sessions -u $1; exit"
        ;;
    *)
        usage
        ;;
esac
