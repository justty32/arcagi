# N8b progress (arcbatch-hot next hotspot) — DONE (see n8b.md: C rejected, D +1.0% not adopted)

## Done (11-10 02:35)
- codex built (`make -C native hot hot-prof hot2 -j4`): `bin/arcbatch-hot-prof` (A+B + rdtsc buckets, `ARC_HOT_PROF=path|-`),
  `bin/arcbatch-hot-c` (A+B + whole MAP/FILTER/ZIPWITH/FOLD result cache, len>=8 only, 64k entries),
  `bin/arcbatch-hot-d` (A+B + thread-local result arena, no C). Code: native/hot/{seed_value.cpp,higher_cache.hpp,result_buffer.hpp,prof/}.
- 1e6 profile (n8b-prof-1e6.txt): FO eval 29.9%, HO loop rest 23.9%, HO lambda body 18.8%, HO result build 10.0%, offer 5.5%, dedup 3.8%, unify 3.7%.
- 1e6 single runs (not official): hot 9.62 s, hot-c 10.00 s, hot-d 9.37 s; all 0/100 mismatches vs arcbatch. See n8b.md.
- Lead: `uv run pytest -q tests/native` 37 passed (outside sandbox). Diff reviewed (Makefile append-only, native/src untouched).

## Running (started 02:35; 1e7 prof DONE -> n8b-prof-1e7.txt, bench still running)
- 1e7 profile: unit `arcagi-n8b-prof-*`, out `/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n8b/prof-1e7-lead/` (profile.txt, DONE), log `/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n8b/prof-1e7.log` (ends `prof=<rc>`).
- Then bench: unit `arcagi-n8b-bench-*`, out `/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n8b/bench-lead/` (wall.txt, cmp.txt, DONE), log `/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n8b/bench.log` (ends `bench=<rc>`).
- Read: `cat /tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n8b/prof-1e7-lead/profile.txt; python3 reports/cpu-hot-1110/analyze.py /tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n8b/bench-lead`

## Remaining (next agent)
1. Paste 1e7 profile table + bench table (with loadavg range from wall.txt, mismatches all 0 in cmp.txt for 1e6 and 1e7) into reports/cpu-hot-1110/n8b.md.
2. Verdict: keep D if >2% median at 1e7; C kept only if it beats hot at 1e7.
3. Commit n8b.md + progress (no jsonl).
