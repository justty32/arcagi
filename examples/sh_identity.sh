#!/bin/sh
# Minimal non-Python solver for the arcagi file protocol (POSIX sh + sed).
#
# Usage: sh sh_identity.sh REQUEST.json RESPONSE.json [TRACE.json]
# Experiment argv: ["sh", "sh_identity.sh", "{input}", "{output}", "{trace}"]
#
# It copies each test input as the prediction (a protocol demo, not a solver).
# The sed extraction relies on the framework's single-line request layout
# (schema_version, task_id, task, seed, params, trace_path in that order);
# real solvers should use a proper JSON parser.
set -eu

request=$1
response=$2
trace=${3:-}

line=$(cat "$request")
task_id=$(printf '%s\n' "$line" |
  sed 's/^{"schema_version": "[^"]*", "task_id": "\([^"]*\)".*$/\1/')
# Keep only the test list: drop everything from the end of "task" on, then
# everything up to "test": [, then unwrap {"input": GRID} objects.
grids=$(printf '%s\n' "$line" |
  sed -e 's/}, "seed": .*$//' -e 's/^.*"test": \[//' -e 's/\]$//' \
      -e 's/{"input": //g' -e 's/}//g')

printf '{"%s": [%s]}\n' "$task_id" "$grids" >"$response"

if [ -n "$trace" ]; then
  cat >"$trace" <<JSON
{"schema_version": "arcagi-trace/1", "solver": "sh_identity",
 "attempts": [{"id": "copy", "kind": "program", "program": "identity",
   "description": "copy every test input unchanged", "selected": true}],
 "selected": "copy",
 "reasoning": "Demo only: training pairs are not checked."}
JSON
fi
