#!/usr/bin/env bash
#
# 08-generate-report.sh
# Dumps hosts, services, vulns and creds out of the workspace into CSV
# files under reports/, and stitches together a bare-bones HTML summary
# so I have something to hand off (or paste into the writeup) without
# rebuilding a table by hand every time.
#
# Usage: ./08-generate-report.sh [workspace]

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
source lib/common.sh

WS_NAME="${1:-$WORKSPACE}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
OUT_DIR="${REPORT_DIR}/${WS_NAME}-${TIMESTAMP}"
mkdir -p "$OUT_DIR"

require_cmd msfconsole

log_info "Exporting workspace '${WS_NAME}' data to ${OUT_DIR}"

msfconsole -q -x "
workspace ${WS_NAME}
hosts -o ${OUT_DIR}/hosts.csv
services -o ${OUT_DIR}/services.csv
vulns -o ${OUT_DIR}/vulns.csv
creds -o ${OUT_DIR}/creds.csv
exit
"

HTML_FILE="${OUT_DIR}/summary.html"
{
    echo "<html><head><title>${WS_NAME} - engagement summary</title>"
    echo "<style>body{font-family:sans-serif;margin:2rem} table{border-collapse:collapse;width:100%;margin-bottom:2rem} td,th{border:1px solid #ccc;padding:6px 10px;text-align:left} th{background:#eee}</style>"
    echo "</head><body>"
    echo "<h1>${WS_NAME} - generated $(date)</h1>"

    for f in hosts services vulns creds; do
        echo "<h2>${f}</h2>"
        csv="${OUT_DIR}/${f}.csv"
        if [[ -s "$csv" ]]; then
            echo "<table>"
            first=1
            while IFS= read -r line; do
                if [[ $first -eq 1 ]]; then
                    echo "<tr><th>$(echo "$line" | sed 's/,/<\/th><th>/g')</th></tr>"
                    first=0
                else
                    echo "<tr><td>$(echo "$line" | sed 's/,/<\/td><td>/g')</td></tr>"
                fi
            done < "$csv"
            echo "</table>"
        else
            echo "<p><em>No data.</em></p>"
        fi
    done

    echo "</body></html>"
} > "$HTML_FILE"

log_info "CSV exports + summary.html written to ${OUT_DIR}"
