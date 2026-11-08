#!/usr/bin/env bash
# Print one line per unread letter in an inbox. Read-only: never moves or
# marks anything. Silent when there is nothing, so it is safe in a hook.
set -uo pipefail

default_inbox=$(cd "$(dirname "$0")/../inbox" 2>/dev/null && pwd) || default_inbox=''
inbox=${1:-${WF_INBOX_SELF:-$default_inbox}}

[ -n "$inbox" ] && [ -d "$inbox" ] || exit 0

for letter in "$inbox"/*.md; do
    [ -f "$letter" ] || continue
    from=''; status=''; headline=''; fm=0; body=0
    while IFS= read -r line || [ -n "$line" ]; do
        if [ "$body" -eq 0 ]; then
            case "$line" in
                '---') if [ "$fm" -eq 0 ]; then fm=1; else body=1; fi ;;
                'from: '*)   [ "$fm" -eq 1 ] && from=${line#from: } ;;
                'status: '*) [ "$fm" -eq 1 ] && status=${line#status: } ;;
            esac
        elif [ -n "$line" ]; then
            case "$line" in '# '*) headline=${line#\# } ;; *) headline=$line ;; esac
            break
        fi
    done < "$letter"
    printf '[INBOX] %s %s — %s — %s\n' \
        "${from:-UNKNOWN}" "${status:-UNKNOWN}" "${headline:-（缺少標題）}" "$letter"
done
