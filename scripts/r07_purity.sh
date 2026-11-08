#!/usr/bin/env bash
# r07 purity gate for the empty-tree seed language (notes/rounds/r07/02 section 1).
#
# Checks, all must pass (exit 0), otherwise exit 1:
#   1. banned domain words in src/arcagi/seed/ and aos/seedlib/ (identifiers,
#      strings and comments alike);
#   2. no banned imports in src/arcagi/seed/;
#   3. aos/seedlib/blocks.json is absent or exactly [];
#   4. `git diff --stat HEAD -- aos/blocks aos/pool` is empty;
#   5. seed.prims.PRIMS has at most 40 entries.
#
# Word rule for check 1: text is split into alphanumeric tokens, camelCase is
# split too (GridSize -> grid size), tokens are lowercased; a token is a hit
# when it fully matches the pattern below. Short ambiguous stems only allow
# their real inflections so that e.g. `col` does not hit `collect`, `row` does
# not hit `arrow`/`throw`, `sym` does not hit `symbol`, `rot` does not hit
# `rotten`-like words, `cell` does not hit `cellar`; distinctive stems (grid,
# flip, crop, shape, pixel, neigh, bbox, fill, mask, paint, stamp, colo[u]r)
# match as prefixes (`fill` hits `fillna`, `filled`; `filter` is fine).
set -u
cd "$(dirname "$0")/.."

fail=0
note() { echo "purity: $*"; }

WORDS='^(grid[a-z0-9]*|rows?|col(s|umn|umns|ored|oring)?|colou?r[a-z0-9]*'
WORDS+='|rot(s|ate|ates|ated|ating|ation|ations)?[0-9]*|flip[a-z0-9]*'
WORDS+='|crop[a-z0-9]*|obj(s|ect[a-z0-9]*|rule[a-z0-9]*)?|shape[a-z0-9]*'
WORDS+='|pixel[a-z0-9]*|cell(s|ular)?|neigh[a-z0-9]*'
WORDS+='|sym(s|metry|metries|metric|metrical)?|bbox[a-z0-9]*|fill[a-z0-9]*'
WORDS+='|mask[a-z0-9]*|paint[a-z0-9]*|stamp[a-z0-9]*)$'

scan_dirs=()
[ -d src/arcagi/seed ] && scan_dirs+=(src/arcagi/seed)
[ -d aos/seedlib ] && scan_dirs+=(aos/seedlib)
if [ ! -d src/arcagi/seed ]; then
  note "missing src/arcagi/seed"; fail=1
fi

# 1. banned words: print file:line:token for each hit.
hits=$(WORDS="$WORDS" python3 - "${scan_dirs[@]}" <<'PY'
import os, re, sys
word = re.compile(os.environ["WORDS"])
tok = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z0-9]+")
exts = {".py", ".json", ".md", ".txt", ".csv", ".sh"}
for root in sys.argv[1:]:
    for d, _, names in sorted(os.walk(root)):
        for name in sorted(names):
            path = os.path.join(d, name)
            if os.path.splitext(name)[1] not in exts:
                continue
            with open(path, encoding="utf-8", errors="replace") as fh:
                for no, line in enumerate(fh, 1):
                    for chunk in re.findall(r"[A-Za-z0-9]+", line):
                        for t in tok.findall(chunk):
                            if word.match(t.lower()):
                                print(f"{path}:{no}:{t.lower()}")
PY
)
if [ -n "$hits" ]; then
  note "banned words found:"; echo "$hits"; fail=1
fi

# 2. banned imports (absolute, relative and string-based).
imp=$(grep -rnE --include='*.py' \
  -e '^\s*(from|import)\s+(arcagi\.(dsl|objrule|blocks|solvers|native)|native|vendor)\b' \
  -e '^\s*from\s+\.\.+\s*import\s+.*\b(dsl|objrule|blocks|solvers|native)\b' \
  -e '^\s*from\s+\.\.+(dsl|objrule|blocks|solvers|native)\b' \
  -e "['\"](arcagi\.)?(dsl|objrule|blocks|solvers|native|vendor)(\.[A-Za-z_.]+)?['\"]" \
  src/arcagi/seed || true)
if [ -n "$imp" ]; then
  note "banned imports:"; echo "$imp"; fail=1
fi

# 2b. r09: src/arcagi/hammer/ must not import the old tree (no word scan).
if [ -d src/arcagi/hammer ]; then
  imp=$(grep -rnE --include='*.py' \
    -e '^\s*(from|import)\s+arcagi\.(dsl|solvers|objrule|blocks|srcspace|shadow|llm)\b' \
    -e '^\s*from\s+\.\.+\s*(import\s+.*\b)?(dsl|solvers|objrule|blocks|srcspace|shadow|llm)\b' \
    src/arcagi/hammer || true)
  if [ -n "$imp" ]; then
    note "banned imports in src/arcagi/hammer:"; echo "$imp"; fail=1
  fi
fi

# 3. seed library must start empty.
lib=aos/seedlib/blocks.json
if [ -e "$lib" ]; then
  if ! python3 -c 'import json,sys; sys.exit(0 if json.load(open(sys.argv[1])) == [] else 1)' "$lib"; then
    note "$lib is not []"; fail=1
  fi
fi

# 4. old tree untouched.
d=$(git diff --stat HEAD -- aos/blocks aos/pool)
if [ -n "$d" ]; then
  note "aos/blocks or aos/pool changed:"; echo "$d"; fail=1
fi

# 5. primitive count.
n=$(PYTHONPATH=src python3 -c 'from arcagi.seed.prims import PRIMS; print(len(PRIMS))' 2>&1)
if ! [[ "$n" =~ ^[0-9]+$ ]] || [ "$n" -gt 40 ]; then
  note "PRIMS count check failed: $n"; fail=1
fi

if [ "$fail" -eq 0 ]; then
  note "ok (prims=$n)"
fi
exit "$fail"
