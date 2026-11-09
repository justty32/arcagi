# N8 progress (cpu-hot-1110) — DONE (bench finished, see README)

## State (01:55, 11-10)
- Built: `make -C native hot` -> native/bin/arcbatch-hot-a (A = lambda call memo, native/hot/seed_value.cpp) and
  native/bin/arcbatch-hot (A+B; B = append-only Subst undo + reused Pick vectors, native/hot/seed_enum.cpp). native/src untouched.
- Lead review: A key = (generation, lam fn, input, args, arity); hit only if steps suffice (steps monotone -> exact);
  insert only when no Store growth; generation bumped on Store::reset and every compile(). B relies on Subst being
  append-only (src/seed_value.hpp:66, unify only emplace_back) -> sound.
- 1e6 single run (codex, under sandbox, load ~10): arcbatch 11.32 s, hot-a 11.67 s, hot 10.00 s; 0/100 mismatches both
  (all keys incl. eval_steps, near). A hit rate 85.97% yet no gain -> lambda bodies are cheap; cost is MAP loop/Store::make.
- `uv run pytest -q tests/native`: 31 passed (lead, outside sandbox; incl. tests/native/test_arcbatch_hot.py).

## Running
- Bench: `bash reports/cpu-hot-1110/bench.sh /tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n8/bench` (self-wraps in scope arcagi-n8-bench-<pid>, nice 19, 4 threads).
  1e6 then 1e7, arcbatch / hot-a / hot interleaved x3 (~30 min). Done when /tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n8/bench/DONE exists; log /tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n8/bench.log.

## Next (new agent)
1. `python3 reports/cpu-hot-1110/analyze.py /tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n8/bench` -> paste table into reports/cpu-hot-1110/README.md (add loadavg from wall.txt);
   check /tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n8/bench/cmp.txt all 0 mismatches for 1e6 and 1e7.
2. Commit README + progress (not the jsonl outputs).
3. If more speed wanted: A gave nothing; next candidate is caching whole MAP/FILTER/ZIPWITH/FOLD results at apply_prim
   level (re-eval inside one generation creates no new Store entries, so the "no store growth" guard is unnecessary there).
