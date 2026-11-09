# M0 baseline (11-10): seed CPU time in six buckets, nodes-to-first, GPU reverse-synthesis prototype

Think-3 route step M0 (`notes/rounds/gpu-night-1109/think-3/代定清單.md` E6) plus the E11/E17 GPU prototype.
Training first 100 tasks (`train100.txt`, sorted filenames), seed mode, decomp on, 4 threads, one run per budget.

## Six-bucket table (exclusive CPU time inside the seed Enumerator)

| bucket | 1e6 s | 1e6 % | 1e7 s | 1e7 % |
|---|---:|---:|---:|---:|
| 1 first-order eval (20 prims except if) | 17.9 | 40.0 | 233.8 | 36.6 |
| 2 lambda eval (map/zipwith/filter/fold) | 17.1 | 38.1 | 292.7 | 45.9 |
|   of which: prim eval incl. lambda body | 15.3 | 34.1 | 284.0 | 44.5 |
|   of which: lambda body pool (enumerate + compile bodies) | 1.8 | 4.1 | 8.7 | 1.4 |
| 3 if eval | 0.06 | 0.1 | 0.5 | 0.1 |
| 4 library block | 0 | 0 | 0 | 0 |
| 5 unify / combinatorics bookkeeping | 7.0 | 15.6 | 77.4 | 12.1 |
|   of which: choose recursion, unify, Subst, emit checks | 3.6 | 8.0 | 37.7 | 5.9 |
|   of which: offer (build prog, bank insert, near score) | 3.4 | 7.6 | 39.7 | 6.2 |
| 6 dedup hash (seen_insert) | 2.5 | 5.6 | 31.5 | 4.9 |
| other: cond_witness | 0.25 | 0.6 | 2.3 | 0.4 |
| total Enumerator CPU s / process wall s | 44.8 / 11.3 | | 638 / 162 | |

Data: [`buckets.csv`](buckets.csv) (9 raw buckets → six), [`summary.txt`](summary.txt) (also per-segment batch-size histogram and nodes per program size).
Eval calls at 1e7: first-order 700M (0.33 µs each), lambda 193M (1.47 µs each, 4.4× a first-order call). Library block is 0 because the base config loads no library.

Nodes-to-first (per-task `nodes_to_first`, [`nodes_to_first.csv`](nodes_to_first.csv)):

| budget | solved (train_ok) | test_ok | nodes-to-first, sorted | median |
|---|---:|---:|---|---:|
| 1e6 | 7 | 5 | 10179, 10789, 54626, 140126, 140128, 241984, 367189 | 140k |
| 1e7 | 10 | 7 | 10179, 10789, 124282, 196491, 475001, 546251, 546251, 950001, 950001, 4873501 | 511k |

Note: the same task can have a larger nodes-to-first at 1e7 than at 1e6 (decomp subproblem budgets scale with the budget), so compare rankers at a fixed budget.

Correctness: `bin/m0prof` rows equal plain `bin/arcbatch` rows (ignoring seconds / eval_steps) at 1e5 (100/100, fresh run) and against the N5c cpu runs at 1e6 and 1e7: 0 mismatches. Overhead of the rdtsc buckets: wall 11.3 s vs 9.1 s (1e6) and 162 s vs 127 s (1e7); the machine was shared with overnight GPU/CPU jobs, so absolute seconds are noisy and the shares are the result.

## GPU reverse-synthesis prototype (E11 / E17)

`native/bin/gpusynth` (`native/gpu/synth/`): each GPU thread takes a training input grid (400 tasks, 1718 train+test inputs), grows a random typed postfix program over the 21 first-order seed prims (add … transpose incl. if), evaluates it while growing, and keeps it if it ends as one non-empty grid different from the input. 30 s run on the shared GPU (100% busy with other units, 244 MB VRAM):

| attempts/s | accepted/s (GPU) | accept rate | unique (input, output) in 30 s | jsonl write |
|---:|---:|---:|---:|---:|
| 1.40M | 111k | 7.6% | 128k of 3.2M accepted (4%) | 100k lines in ~1.2 s host |

Sample rows: [`gpusynth-sample.jsonl`](gpusynth-sample.jsonl) (`prog` is in seed s-expr form). Limits: semantics are re-implemented and NOT cross-checked against `seed_value.cpp`; program space is shallow first-order only (most accepted programs are reverse/transpose/take/drop variants, hence 4% unique); no lambdas, no ranker training.

## Plain-language reading

Most of the seed search time really is evaluating candidates: about 78% (1e6) to 83% (1e7) of CPU time. But it is split almost evenly between plain first-order primitives and the lambda primitives, and the lambda share grows with budget (38% → 46%) because each lambda call is about 4× as expensive. Bookkeeping (type matching, building programs, putting them in the bank, hashing to remove duplicates) is only 17–21%. `if` and library blocks are negligible. So a GPU that made only first-order evaluation free would cap at about 1.6×; making lambda evaluation free would cap at about 1.9×; both together about 5.7×. The search still solves only 7 (1e6) or 10 (1e7) of 100 tasks, so there are very few solved programs to learn from. The GPU can manufacture about 100k (input, program, output) samples per second even while shared, but most are duplicates; diversity, not speed, is the bottleneck.

## Effect on E1 / E5 / E7

- **E1** (GPU on outer loop vs inner loop): its flip condition was "evaluation ≥90% → lambda kernel early". Measured evaluation share is 78–83%, below 90%. E1 stays B (ranker first). Inner-loop ceiling: ~5.7× only if both first-order and lambda eval move to GPU.
- **E5** (lambda kernel gate: map+zipwith+if eval ≥50% and host bookkeeping ≤25% at 1e7): bookkeeping 17% (≤25%, met); lambda+if eval 46.0% (<50%, not met, borderline), and that 46% still includes filter/fold, so map+zipwith alone is lower. Gate not met; L1 stays gated. It rises with budget, so recheck at 1e8 or with the R1 ranker on (the ranker shortens runs, which pushes the share down, not up).
- **E7** (R1 ranker gate): baseline nodes-to-first median 140k at 1e6 (7 solved), 511k at 1e7 (10 solved). R1 "continue" needs ≤70k median at 1e6 with ≥7 solved. 7–10 solved tasks are too few to learn a prior from, which supports E11 (expand data first); the gpusynth prototype shows raw volume is cheap, but it needs dedup by (input, output) and deeper/lambda programs before it is useful training data.
- E14 (batch sizes): per-(op,split) segments are mostly small (at 1e7, 56% of 412k segments have <256 nodes), which matches the known small-launch problem for any per-segment GPU kernel. E18 (cross-example collapse share) was not measured.

## Reproduce

```
make -C native m0prof gpusynth
bash reports/m0-baseline-1110/run.sh <rawdir>      # 1e6 + 1e7, ~3 min with 4 threads
python3 -I reports/m0-baseline-1110/analyze.py <rawdir> reports/m0-baseline-1110 [<n5c dir with res-<B>-cpu-1.jsonl>]
python3 -I native/gpu/synth/prep.py data/ARC-AGI/data/training <grids.bin> <names.json>
native/bin/gpusynth --grids <grids.bin> --names <names.json> --seconds 30 --batch 262144 --write 100000 --out <scratch>/synth.jsonl
```

Code: `native/gpu/seed/m0prof.hpp` (bucket timers), `native/gpu/seed/m0prof_mk.py` (generates `m0prof_enum.cpp` from `src/seed_enum.cpp`; `src/` untouched), `native/gpu/seed/m0prof_main.cpp`, `native/gpu/synth/{gpusynth.cu,prep.py}`, `native/Makefile` (appended targets `m0prof`, `gpusynth`).
Raw outputs (not committed): `/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n6/raw/`, synthetic samples `/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n6/synth-30s.jsonl` (37 MB).
