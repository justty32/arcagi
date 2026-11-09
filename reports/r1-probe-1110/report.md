# R1 probe (11-10): cost-bucketed seed enumeration with a gpusynth prior

Think-3 E7 / E11–E19 probe, with Argon's fix applied (`02b-Argon審.md` item 2 and proposal 4): no "defer but keep" per layer. Instead the bank is built by **integer cost bucket** (Levin style), with cost = sum of −log prior. Measurement only; not on the main line.
Setup: training first 100 (`reports/m0-baseline-1110/train100.txt`), seed mode, decomp on, 4 threads, one run per budget. All runs were sequential on the same machine.

## What was built

- **Prior** (`mkprior.py` → [`prior.json`](prior.json), [`costs.txt`](costs.txt)): streams 1,193,192 gpusynth v2 rows (5-min file, `n6b/v2-5m.jsonl`). It counts each primitive node by (declared return class int/bool/list/poly, depth from root 0–6+) and applies add-one smoothing within each class. `prior.json` has `P(prim | class, depth)` and the depth marginal `P(prim | class)`.
- **Costs**: w(op) = 1 + round(log4(p_max_in_class / p)), clipped to [1, 3]. map/filter/zipwith/fold get 1 (neutral) because gpusynth is first-order and cannot produce them. Resulting costs: 1 = eq lt len range repeat sort head last (+ the 4 lambda ops); 2 = not add neg take drop reverse cons append concat transpose nth; 3 = and or sub mul mod max min count if.
  - Depth is **not** used in the binary. Bottom-up enumeration does not know a node's depth from the root, so the binary uses the depth marginal. The depth table is kept in `prior.json` for later.
- **Probe binary** `native/bin/arcbatch-r1` (`make -C native r1`):
  - `native/gpu/seed/r1_mk.py` generates `r1_enum.cpp` from `src/seed_enum.cpp` (`src/` untouched, same approach as m0prof). `r1_main.cpp` is the wrapper.
  - Bank level k holds programs of cost k: cost(op(c…)) = w(op) + Σ cost(c), leaves cost 1, lambda bodies keep cost = size. Cost buckets run from low to high. Every (op, split) of every bucket is still enumerated, so **nothing is dropped**. Only the order changes, along with which observationally equal program is kept as a value's representative.
  - Costs are read from `$ARC_R1_COSTS`. With no file set, all costs are 1 and the run is identical to `arcbatch`.
- R1-lite (same-layer sort) was not needed: cost bucketing fit the bottom-up bank directly (a 3-line change to the size loop).
- Extra variant **lam2** ([`costs-lam2.txt`](costs-lam2.txt)): same costs, but the 4 lambda ops cost 2. It tests why r1's wall time doubled (see below).

## Correctness / solution-set consistency

| check | result |
|---|---|
| `arcbatch-r1` without costs vs `arcbatch` @1e6, all row fields except seconds | 100 rows, **0 mismatches** |
| solved set (train_ok), r1 vs base @1e6 / @1e7 | **0 / 0** tasks differ |
| solved set, lam2 vs base @1e6 / @1e7 | 0 / **1** differs (lam2 loses 27a28665 @1e7) |
| test_ok set, r1 vs base | @1e6 r1 gains 2dee498d (+1); @1e7 identical |

Where a task is solved by both, the program found can differ (another program with the same train outputs). Listed in [`analyze-out.txt`](analyze-out.txt).

## Results

| budget | engine | solved | test_ok | nodes-to-first median | sorted | wall s | Σ eval_steps |
|---|---|---:|---:|---:|---|---:|---:|
| 1e6 | base | 7 | 5 | 140,126 | 10179, 10789, 54626, 140126, 140128, 241984, 367189 | 8.7 | 0.24 G |
| 1e6 | r1 | 7 | 6 | **47,501** (0.34×) | 12668, 32412, 46681, 47501, 54626, 140128, 238938 | 17.0 (+95%) | 1.22 G (5.0×) |
| 1e6 | lam2 | 7 | 5 | 54,626 (0.39×) | 20361, 30632, 47501, 54626, 54626, 140126, 242723 | 12.1 (+38%) | 0.45 G (1.9×) |
| 1e7 | base | 10 | 7 | 510,626 | 10179 … 4873501 | 125.0 | 4.8 G |
| 1e7 | r1 | 10 | 7 | 546,251 (1.07×) | 12668, 32412, 46681, 475001, 546251, 546251, 855001, 950001, 950001, 2376438 | 230.0 (+84%) | 19.7 G (4.1×) |
| 1e7 | lam2 | 9 | 6 | 546,251 (1.07×) | 20361 … 2380223 | 152.3 (+22%) | 9.8 G (2.0×) |

Per-task r1/base nodes-to-first on commonly solved tasks:
- 1e6:
  - median ratio **1.00**
  - faster: 239be575 367k→48k, 2dee498d 140k→32k
  - slower: 25ff71a9 10k→47k, 3c9b0459 10.8k→12.7k
  - 3 tasks unchanged
- 1e7:
  - median ratio **1.00**
  - faster: 445eab21 4.87M→0.86M, 2dee498d 124k→32k
  - slower: 1e0a9b12 196k→2.38M (12×), 25ff71a9, 3c9b0459
- Several 1e7 values (475001, 546251, 950001) are the same in every engine. These tasks are solved through decomp subproblems, and their counter does not move.

## E7 reading (gate: nodes-to-first ≤0.5×, solved ≥ baseline, wall overhead ≤5%)

| | ≤0.5× nodes | solved ≥ base | wall ≤ +5% | verdict |
|---|---|---|---|---|
| r1 @1e6 | 0.34× pooled (yes), but paired per-task median 1.00× | 7 = 7 yes | +95% no | **fail** |
| r1 @1e7 | 1.07× no | 10 = 10 yes | +84% no | **fail** |
| lam2 @1e6 / @1e7 | 0.39× / 1.07× | 7=7 / 9<10 | +38% / +22% | **fail** |

The ≤70k@1e6 number is met only as a pooled median. That comes from a reshuffle among 7 tasks (2 got much faster, 2 got slower), not a uniform shift. The paired median is 1.0, and at 1e7 there is no gain. This is exactly the N=7 fragility Argon item 1 warned about. **E7: do not continue R1 in this form.**

## In plain words

Reordering the search by "how common each primitive is in the GPU-made samples" never loses a solution: the solved tasks are the same, and with all costs equal it reproduces the original exactly. But it does not make the search reliably faster. Two tasks got 4–8× faster, others got slower, and the typical task is unchanged. It also costs a lot of wall time: the same number of candidates takes about 2× as long. The prior is learned from first-order samples only, so the lambda primitives (map/filter/…) stay cheap, and the search spends more of its budget on expensive lambda candidates (5× the eval steps). Making lambdas cost 2 removes most of that overhead but loses one task at 1e7. The prior mainly reflects how the generator samples, not what ARC tasks need. With 7–10 solved tasks there is not enough signal to tell a good prior from noise.

## Next steps

1. Measure the ranker in **eval steps or wall time to first solution**, not nodes, and put expected eval cost into w(op). Otherwise any prior that favours lambdas looks good on nodes and loses on wall time.
2. Condition the cost on **task I/O invariants** (Argon proposal 4: same shape, length kept, colour subset). This gives a per-task w(op | I) that needs no training data.
3. A prior needs data from programs with lambdas (gpusynth with map/zipwith, or E11 bank-hindsight samples) before lambda costs can come from evidence instead of being set by hand.
4. Judge on more solved tasks (all 400 training tasks at 1e7, or the 1e8 runs) so the median is not decided by 7 tasks.

## Reproduce

```
python3 -I reports/r1-probe-1110/mkprior.py <v2-5m.jsonl> reports/r1-probe-1110/prior.json reports/r1-probe-1110/costs.txt   # ~9 s
make -C native r1
bash reports/r1-probe-1110/run.sh <rawdir>          # id@1e6, base/r1 @1e6 and @1e7 (~7 min)
# lam2: ARC_R1_COSTS=reports/r1-probe-1110/costs-lam2.txt native/bin/arcbatch-r1 --mode seed ... (same flags)
python3 -I reports/r1-probe-1110/analyze.py <rawdir>
```
Raw rows (not committed): `/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n7/raw/`.
