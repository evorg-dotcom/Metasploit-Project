#!/usr/bin/env bash
#
# 09-db-backup-restore.sh
# Backs up (or restores) the Metasploit postgres database. Mostly
# exists because I've wiped my workspace history by accident once
# already and didn't want to do that again mid-engagement.
#
# Usage: ./09-db-backup-restore.sh backup [output-file]
#        ./09-db-backup-restore.sh restore <input-file>

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source lib/common.sh

usage() {
    echo "Usage: $0 backup [output-file]"
    echo "       $0 restore <input-file>"
    exit 1
}

[[ $# -ge 1 ]] || usage
ACTION="$1"
shift || true

require_cmd pg_dump
require_cmd pg_restore

# Metasploit stores its db creds here after `msfdb init`
DB_CONF="${HOME}/.msf4/database.yml"
if [[ ! -f "$DB_CONF" ]]; then
    log_err "Can't find $DB_CONF - has msfdb been initialized on this box?"
    exit 1
fi

DB_NAME="$(grep -A6 '^production:' "$DB_CONF" | grep 'database:' | awk '{print $2}')"
DB_USER="$(grep -A6 '^production:' "$DB_CONF" | grep 'username:' | awk '{print $2}')"

: "${DB_NAME:=msf}"
: "${DB_USER:=msf}"

BACKUP_DIR="${REPORT_DIR}/../backups"
mkdir -p "$BACKUP_DIR"

case "$ACTION" in
    backup)
        OUT="${1:-${BACKUP_DIR}/msf-$(date +%Y%m%d-%H%M%S).dump}"
        log_info "Backing up database '${DB_NAME}' -> ${OUT}"
        PGPASSWORD="${PGPASSWORD:-}" pg_dump -U "$DB_USER" -Fc -f "$OUT" "$DB_NAME"
        log_info "Backup complete: ${OUT}"
        ;;
    restore)
        [[ $# -ge 1 ]] || usage
        IN="$1"
        [[ -f "$IN" ]] || { log_err "File not found: $IN"; exit 1; }
        log_warn "This will restore into '${DB_NAME}' - existing data may be overwritten."
        read -r -p "Continue? [y/N] " confirm
        [[ "$confirm" =~ ^[Yy]$ ]] || { log_info "Cancelled."; exit 0; }
        PGPASSWORD="${PGPASSWORD:-}" pg_restore -U "$DB_USER" -d "$DB_NAME" --clean --if-exists "$IN"
        log_info "Restore complete."
        ;;
    *)
        usage
        ;;
esac
