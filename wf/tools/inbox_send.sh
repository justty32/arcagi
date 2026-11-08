#!/usr/bin/env bash
# Deliver one letter into another agent's inbox. Atomic: write a temp file in
# the destination inbox, then mv into place. See workflows/inbox/PROTOCOL.md.
set -uo pipefail

usage() {
    printf 'Usage: %s [--reply-to <path>] <dest_inbox> <sender> <STATUS> <headline> [body_file]\n' "${0##*/}" >&2
    printf '  STATUS: REQUEST | DONE | BLOCKED | NEEDS-USER | FAILED | PROGRESS\n' >&2
    printf '  body read from stdin when body_file is omitted\n' >&2
}

fail() { printf 'inbox_send: %s\n' "$1" >&2; exit 1; }

# Default reply address: WF_INBOX_SELF, else <this script>/../inbox.
self_default=$(cd "$(dirname "$0")/../inbox" 2>/dev/null && pwd) || self_default=''
reply_to=${WF_INBOX_SELF:-$self_default}

if [ "${1-}" = '--reply-to' ]; then
    [ $# -ge 2 ] || { usage; exit 2; }
    reply_to=$2
    shift 2
fi

if [ $# -lt 4 ] || [ $# -gt 5 ]; then usage; exit 2; fi

dest=$1
sender=$2
status=$3
headline=$4
body_file=${5-}

case "$sender" in
    ''|*[!A-Za-z0-9._-]*) fail 'sender may contain only letters, digits, dot, underscore, hyphen' ;;
esac

case "$status" in
    REQUEST|DONE|BLOCKED|NEEDS-USER|FAILED|PROGRESS) ;;
    *) fail "invalid STATUS '$status' (see PROTOCOL.md)" ;;
esac

if [[ -z $headline || $headline == *$'\n'* || $headline == *$'\r'* ]]; then
    fail 'headline must be one non-empty line'
fi

[ -d "$dest" ] || fail "destination inbox does not exist: $dest"
[ -w "$dest" ] || fail "destination inbox is not writable: $dest"
[ -z "$body_file" ] || [ -r "$body_file" ] || fail "body file is not readable: $body_file"

clock=$(date '+%Y%m%dT%H%M|%Y-%m-%dT%H:%M:%S%z') || fail 'cannot read the current time'
stamp=${clock%%|*}
at=${clock#*|}

target="$dest/${stamp}-${sender}-${status}.md"
[ ! -e "$target" ] || fail "a letter already exists for this minute/sender/status: $target"

tmp=$(mktemp "$dest/.inbox-send.XXXXXX") || fail "cannot create a temp file in: $dest"
trap 'rm -f -- "$tmp" 2>/dev/null || true' EXIT
trap 'exit 130' HUP INT TERM

{
    printf -- '---\n'
    printf 'from: %s\n' "$sender"
    printf 'to: %s\n' "$(basename "$(dirname "$dest")")"
    printf 'status: %s\n' "$status"
    printf 'at: %s\n' "$at"
    [ -n "$reply_to" ] && printf 'reply-to: %s\n' "$reply_to"
    printf -- '---\n'
    printf '# %s\n\n' "$headline"
    if [ -n "$body_file" ]; then cat -- "$body_file"; else cat; fi
} > "$tmp" || fail 'could not write the letter body'

mv -- "$tmp" "$target" || fail "cannot publish the letter to: $target"
trap - EXIT
printf '%s\n' "$target"
