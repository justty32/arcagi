#!/bin/sh
# Round-6 full evaluation through the native hybrid entry (Python search first,
# C++ fills in, Python re-verifies). Parameters follow reports/native-s1/04-總結.md.
#
# Usage: scripts/eval_r06.sh {training|evaluation} <name> [--tasks ID,ID,...] [extra eval args]
#   --tasks  copies those task JSONs into artifacts/<name>/<split>-tasks/ and
#            evaluates only them (for trial runs); other args go to `arcagi eval`.
# Outputs: artifacts/<name>/<split>.json, <split>-traces.jsonl, <split>-env.txt
# Env ARCAGI_MEM overrides the 16G memory cap (sub-lines use 8G).
set -eu
cd "$(dirname "$0")/.." || exit 1

if [ $# -lt 2 ]; then
    sed -n '5,8p' "$0" >&2
    exit 2
fi
split=$1
name=$2
shift 2
case $split in
training | evaluation) ;;
*)
    echo "split must be training or evaluation" >&2
    exit 2
    ;;
esac

# Only real eval processes (uv / python / arcagi argv[0]), not e.g. an agent
# whose prompt text happens to contain "arcagi eval".
running=$(pgrep -af "arcagi eval" | grep -E '^[0-9]+ ([^ ]*/)?(uv|python[0-9.]*|arcagi) ' || true)
if [ -n "$running" ]; then
    echo "another 'arcagi eval' is running; not starting:" >&2
    echo "$running" >&2
    exit 1
fi

out=artifacts/$name
mkdir -p "$out"
select=""
if [ "${1:-}" = "--tasks" ]; then
    dir=$out/$split-tasks
    rm -rf "$dir"
    mkdir -p "$dir"
    for id in $(echo "$2" | tr ',' ' '); do
        cp "data/ARC-AGI/data/$split/$id.json" "$dir/"
    done
    select="--tasks-dir $dir"
    shift 2
fi

{
    echo "date: $(date -Iseconds)"
    echo "split: $split"
    echo "name: $name"
    echo "head: $(git rev-parse HEAD)"
    echo "extra args: $select $*"
    echo "git status --short native:"
    git status --short native
} >"$out/$split-env.txt"

# shellcheck disable=SC2086 # $select is intentionally split into two words
exec systemd-run --user --scope -q -p "MemoryMax=${ARCAGI_MEM:-16G}" nice -n 19 \
    uv run arcagi eval --split "$split" $select --name "$name" \
    --external 'native/bin/solve {input} {output} {trace}' \
    --timeout 40 --workers 6 \
    --output "$out/$split.json" --traces "$out/$split-traces.jsonl" "$@"
