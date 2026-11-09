# Task: write `gpuprofile`, a GPU "near-miss profile" tool (C++/CUDA)

Repo root: /home/lorkhan/repo/arcagi. You work in `native/gpu/profile/` (your cwd) plus one
appended target in `native/Makefile`.

## Safety boundary (must follow exactly)
- Write ONLY: `native/gpu/profile/` (new files). Everything else is read-only, `data/` read-only.
- Do NOT modify or overwrite `native/gpu/*.cu|*.cpp|*.hpp`, `native/gpu/gp/*`, `native/src/*`,
  `native/bin/gpusearch*` (long runs are using them). No sudo, no package installs, no system
  config changes, no rm inside the project, no network, do not read ~/.ssh / keyrings / secrets.
- Do not run anything on the GPU, do not run long jobs. You may compile (`make -C .. gpuprofile`
  from native/, i.e. `make -C /home/lorkhan/repo/arcagi/native gpuprofile`) if nvcc works in your sandbox; if not, just make the code
  as correct as you can.
- Do NOT write tests, do NOT write evidence/report/README files. Code comments in English.

## Read first
- `native/gpu/kernel.cu`, `native/gpu/space.hpp`, `native/gpu/gpu.hpp` (N2 evaluator: primitives
  `apply`, `run_steps`, `decode`, `Verdict`, `c_alpha`, `c_task`, kernels `k_shared`, host `gpu_*`).
- `native/gpu/driver.cpp` (host: task loading, `alphabet()`, `to_step()`, `decode()`,
  `run_all()`, `unique_prefixes()`, `pack()`, arg parsing). All in an anonymous namespace, so COPY
  the helpers you need into your own file (do not edit driver.cpp).
- `native/gpu/gp/gp_kernel.cu` line 1-2 and the Makefile `gpugp` target: that is the pattern to
  follow — your .cu does `#include "../kernel.cu"` to reuse all device primitives, and you link
  `$(LIB_OBJECTS)` + your two objects (NOT bin/gpu-obj/kernel.o or driver.o).

## Files to create
- `native/gpu/profile/profile.hpp` — host API of your kernel.
- `native/gpu/profile/profile_kernel.cu` — `#include "../kernel.cu"`, new kernel + host wrappers.
- `native/gpu/profile/profile_main.cpp` — CLI.
- The Makefile `gpuprofile` target is ALREADY appended (read the end of native/Makefile); do not edit the Makefile at all.

## What the tool computes
Same program space as gpusearch (per-task alphabet from `alphabet()`, programs = sequences of
1..depth steps, optional `--dedup P` unique-prefix mode exactly like gpusearch). But instead of
only exact solutions it scores EVERY program by how close it gets to the train outputs, and keeps
the top programs per depth.

### Score of one program (device), over TRAIN pairs only
For each train pair p: run the program on input p (`run_steps`). If any step fails / goes out of
bounds (as in run_steps returning nullptr) the program is INVALID (counted in `n_fail`, no score).
Otherwise with output (h,w), target (th,tw):
- `denom += max(h*w, th*tw)`
- for the overlap region y < min(h,th), x < min(w,tw): `same += cur[y*w+x] == tg[y*tw+x]`,
  and `cnt[cur][tg]++` (cnt is 11x10 uint16/int, shared across ALL train pairs of the program).
Then `raw = same/denom`, `mapped = sum over s in 0..10 of max_g cnt[s][g]`, `cm = mapped/denom`
(cm >= raw always; cm is the score after the best single consistent colormap).
`score = cm`. `perfect` iff `mapped == denom` (integer compare). Quantize: `q = (uint32)(cm*65535+0.5)`,
`rq` likewise for raw.
Consequence to preserve: an exact gpusearch solution or a gpusearch colormap solution has q == 65535.

### Kernel `k_profile`
Structure like `k_shared`: one thread = one depth-1 prefix (pidx, decoded with `decode(pidx, A, 0,
depth-1, plen, prefixes, prog)`); cache the pair-0 prefix state once (as k_shared does), then for
each last step s in 0..A-1: apply on the cached pair-0 state, then run the full program on train
pairs 1..ntrain-1 with `run_steps`, accumulating the score above. NO early exit on mismatch
(we want near misses). Program index = pidx*A + s (same encoding as gpusearch, so the host
`decode` from driver.cpp works).
Per valid program:
- shared-memory block histogram of 1024 bins (bin = q >> 6), flushed with atomicAdd to a global
  `hist[1024]` (uint64 or uint32 per launch — uint32 per launch is fine, host accumulates into uint64).
- atomicAdd global counters: `n_valid`, `n_perfect`; invalid ones: `n_fail` (uint64 via
  `unsigned long long` atomics).
- if `q >= thr_q` (kernel arg): `slot = atomicAdd(nhit,1)`; if `slot < cap` write
  `hits[slot] = {idx (uint64), q (uint32), rq (uint32)}`.
Stack: keep per-thread arrays like k_shared (ba, bb, bt, bp, st, cnt). Set
`cudaDeviceSetLimit(cudaLimitStackSize, 8192)` like gpu_open.

### Host wrappers (profile_kernel.cu)
Your own context struct (device buffers inputs/targets/prefixes/hits/hist/counters), functions:
open(cap), close, load(DTask, inputs, targets, alpha) (copy to `c_task`/`c_alpha` symbols — they are
visible since you include kernel.cu), set_prefixes(table, plen), and
`run(depth, start, count, use_prefix, thr_q, out_hits, out_hist[1024], out counters) -> nhit_true`.
`count` = number of prefix threads; block 128.

### Host driver (profile_main.cpp)
CLI: `gpuprofile --tasks LIST [--data-dir DIR] | --task FILE ... --depth D (default 4)
--dedup P (default 0, P<=4) --budget SEC (per task, default 60) --topk K (default 8)
--pool M (default 64) --chunk N (default 1<<22 programs per launch) --cap N (default 1<<16)
--spec PATH (default native/spec.json) --out JSONL (append)`.
Task list format & loading as gpusearch (skip tasks with > MAX_PAIRS inputs: write
`{"task":id,"skipped":"too many pairs"}`).

Per task: build alphabet, DTask, load. For d = 1..depth while time < budget:
- prefix mode exactly as gpusearch (`use_prefix = dedup>0 && d>dedup`, build `unique_prefixes`
  once, record `prefixes` object like gpusearch; if rows==0 stop).
- total programs = (use_prefix ? rows*A^(d-plen) : A^d); threads = total/A; chunk in threads =
  max(1, chunk/A). For each chunk (check budget before each; on timeout mark depth incomplete and stop
  the task after this depth):
  - thr_q = current per-depth threshold (0 initially; once the per-depth pool holds M entries,
    thr_q = q of the M-th best).
  - run; if nhit > cap: compute thr2 from this launch's histogram = lower q bound (bin<<6) of the
    highest bin b such that the count of programs in bins >= b is >= M. If thr2 > thr_q rerun the
    same chunk once with thr2 (use only the rerun's hist/counters); otherwise keep the truncated
    hits and set `truncated=true` for that depth.
  - add hist/counters to the depth totals; merge hits into the depth pool (keep best M by
    (q desc, rq desc, idx asc)).
- After the depth: materialise the pool on CPU in order: decode word -> Program (driver.cpp
  `decode`, with prefix table when used), run `run_all` on the TRAIN inputs, compute a signature of
  the train outputs (e.g. `signature(grids, n)` from native/src as driver.cpp uses) and keep the first
  K entries with distinct signatures (drop programs that fail on CPU). For each kept entry output
  `{"program": <arcagi JSON program, steps as to_step() gives>, "score": q/65535, "raw": rq/65535,
  "ops": [op name of each step, e.g. "rot180","colormap","upscale"]}`.
Per-depth JSON: `{"d", "space" (programs launched), "valid", "fail", "perfect", "seconds",
"complete", "truncated", "best" (score of top-1 or 0), "ge": {"50":n,"80":n,"90":n,"95":n,"99":n}
(valid programs with q >= 0.50*65535 etc., from the histogram bins: bin >= ceil(frac*1024)),
"hist20": [20 counts, bins of width 0.05 over score, last bin includes 1.0], "top": [...]}`.
Task record (one JSON line, flushed): `{"task", "alphabet", "max_depth", "dedup", "seconds",
"prefixes"? , "depths": [...], "best": max best over depths, "best_depth": shallowest depth reaching
it, "perfect_depth": shallowest depth with perfect>0 or 0}`.
Use the repo Json type the way driver.cpp does.

## Done when
`make -C /home/lorkhan/repo/arcagi/native gpuprofile` builds `native/bin/gpuprofile` with no errors
(or, if nvcc is unavailable in your sandbox, the code is complete and you say so), and the only
changed paths are the three new files under native/gpu/profile/ and the appended Makefile target.
Report in a few lines: files, any deviations from this spec, compile status.
