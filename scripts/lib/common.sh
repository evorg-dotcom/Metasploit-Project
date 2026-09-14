#!/usr/bin/env bash
# Shared helpers sourced by the other scripts in this folder.
# Not meant to be run directly.

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[+]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[!]${NC} $*"; }
log_err()  { echo -e "${RED}[-]${NC} $*" 1>&2; }

require_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        log_err "'$1' is required but not installed. Aborting."
        exit 1
    fi
}

require_root() {
    if [[ $EUID -ne 0 ]]; then
        log_err "This needs to be run as root (or with sudo)."
        exit 1
    fi
}

# Default workspace name, override with MSF_WORKSPACE env var
WORKSPACE="${MSF_WORKSPACE:-lab}"

REPORT_DIR="${MSF_REPORT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/reports}"
LOOT_DIR="${MSF_LOOT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/loot}"

mkdir -p "$REPORT_DIR" "$LOOT_DIR" 2>/dev/null || true
