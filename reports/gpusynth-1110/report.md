# gpusynth v2: checked semantics and more diverse output (think-3 E11)

The GPU training-data generator `native/bin/gpusynth` now matches the CPU seed interpreter on every sample we checked (0 mismatches). Over 30 s it keeps 31% of its accepted samples as distinct, up from 4%. It is the first source that writes deduplicated (input, program, output) rows. The 10× distinct-count goal was not met: v2 has 2.3× as many distinct samples in 30 s.

## What changed

- `native/gpu/synth/gpusynth.cu` (v2):
  - 28 first-order seed primitives. v1 had 21; v2 adds `cons append concat range repeat count sort`.
  - Semantics rewritten line by line against `native/src/seed_value.cpp`. Three behaviours changed: `take`/`drop` with n<0 now act as n=0 (v1 rejected the program); `and`/`or` return their operands in Python style; `mod` uses the seed sign rule.
  - The typed model is stricter than the CPU, never looser. It rejects ragged grids, `if` with branches of different kinds, list values outside int8 and sort of grids taller than 64 rows. So every program it accepts must evaluate the same way on the CPU.
- Diversity:
  - Grid choice is stratified (global thread index mod 1718 grids).
  - Each thread draws a target length uniformly from [mint=4, maxt=12] (depth strata).
  - reverse/transpose/take/drop get weight 1 (others 4), and an immediate repeat of reverse, transpose, sort, neg or not is banned.
  - Past the target length the walk stops pushing new values, and it falls back to the last valid prefix of at least 4 tokens.
  - The host dedups by output fingerprint: (grid, output grid) keeps only the shortest program.
  - `--stratum-cap N` caps rows per (root primitive, length) when writing.
  - The output of each kept row is recomputed on the host with the same `step()`.
- `native/gpu/synth/verify.cpp` → `bin/gpusynth_verify` (`make gpusynth-verify`, appended to `native/Makefile`). It reservoir-samples N rows, runs `seed::compile` + `seed::eval` on the real task input and compares the result with `out` exactly (Json ==). `--only a,b` restricts the check to rows that use the named primitives.
- The old binary is kept as `native/bin/gpusynth-v1` for the before/after runs.
- I did not reuse the N5b kernel (`gpu/seed/`). It evaluates inside the enumerator's value bank, and gpusynth needs a single stack walk. The independent CPU check below stands in for that reuse.

## 1. Semantic check (CPU `seed_value.cpp` is the reference)

| file | rows checked | mismatches | CPU eval errors |
|---|---:|---:|---:|
| v1 30 s file (old, `n6/synth-30s.jsonl`) | 10,000 random | 0 | 0 |
| v2 30 s, uniform | 10,000 random | 0 | 0 |
| v2 30 s, rows using `and or not eq lt if count mod mul min max` | 10,000 | 0 | 0 |
| v2 5 min, uniform | 10,000 random | 0 | 0 |
| v2 5 min, every row using `if eq lt not count` | 5,053 (all of them) | 0 | 0 |

Per-primitive coverage (rows checked containing the primitive, all with 0 mismatches) is in `verify-*.json`.

**Gap:** `and` and `or` never occur in any written v2 row, and they occur in no v1 sample either. They need two booleans on the stack whose result then feeds `if`, which random walks almost never build. They are not empirically verified. Their code is `x ? y : x` and `x ? x : y` on bools only, which is the `seed_value.cpp` rule. `eq`, `lt`, `not` and `if` are covered by only 158, 158, 66 and 316 rows.

## 2. Diversity before and after (same shared GPU, at 100% use by other units, run back to back)

| run | attempts/s | accepted | distinct (grid, output) | distinct share | distinct/s |
|---|---:|---:|---:|---:|---:|
| v1, 30 s | 1.59M | 3,627,383 | 134,657 | 3.7% | 4.5k |
| v2, 30 s | 1.13M | 981,613 | 305,930 | **31.2%** | **10.2k** |
| v2, 5 min (the 30 s mark of the same run) | 1.19M | 943,449 at 30 s | 298,464 at 30 s | 31.6% | 9.9k |
| v2, 5 min (whole run) | 1.19M | 10,371,482 | **1,193,192** | 11.5% | 4.0k |

- The goal "distinct share ≥30% in 30 s" is met (31.2%). The goal "≥10× distinct count" is not: v2 reaches 2.3× in 30 s and 8.9× v1's 30 s count only over 5 min.
- The distinct rate falls over time: 10k/s for the first 30 s, 4k/s averaged over 5 min. The short programs that 1718 grids can reach are running out, and 333k accepted samples replaced a longer program that had the same output.
- In the 30 s comparison v2 accepts fewer samples (2.9% vs 7.6%) because its programs are longer and more of their walks die. It still yields 2.3× as many distinct samples.

## 3. The 5-minute dataset

- File: `/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n6b/v2-5m.jsonl` (521 MB, 1,193,192 rows, not committed; it sits on tmpfs). 200 random rows are in [`sample.jsonl`](sample.jsonl).
- Summaries: [`v2-5m.json`](v2-5m.json), [`v2-30s.json`](v2-30s.json), [`v1-30s.json`](v1-30s.json).
- Program length (tokens 4..12): 160k, 187k, 223k, 184k, 143k, 109k, 83k, 61k, 44k.
- Root primitive:

  | root | rows | share |
  |---|---:|---:|
  | repeat | 507,845 | 42.6% |
  | append | 164,594 | 13.8% |
  | cons | 139,418 | 11.7% |
  | sort | 115,546 | 9.7% |
  | transpose | 108,902 | 9.1% |
  | reverse | 70,225 | 5.9% |
  | drop | 45,820 | 3.8% |
  | take | 40,801 | 3.4% |
  | if | 41 | ~0% |

  reverse/transpose/take/drop together are 22% of roots. In v1 they were nearly all of them: reverse appears in 51% and transpose in 53% of v1 rows.
- Rows that use each primitive (out of 1.19M):

  | primitive | rows | primitive | rows | primitive | rows |
  |---|---:|---|---:|---|---:|
  | repeat | 675k | transpose | 321k | add | 58k |
  | sort | 619k | reverse | 302k | neg | 54k |
  | last | 362k | head | 291k | mul | 45k |
  | range | 359k | append | 288k | max | 35k |
  | len | 376k | cons | 271k | sub | 33k |
  | concat | 161k | nth | 121k | min | 24k |
  | drop | 116k | take | 110k | mod | 20k |
  | count | 4.7k | if | 316 | eq, lt | 158 each |
  | not | 66 | and, or | 0 | | |

## Plain-language reading

The generator writes small random programs, runs them on real ARC input grids and keeps the program together with its output as a training example. We checked its arithmetic against the real CPU interpreter on about 45,000 examples and every one matched, so the examples can be trusted. It used to make the same few flips and crops over and over: only 4 in 100 examples were new. Now it uses more building blocks (stacking, repeating, sorting rows), aims for longer programs and throws away repeats. About 31 in 100 examples in the first 30 s are new, and it produces about 10,000 new examples per second at first. Five minutes gives 1.2 million distinct examples. They are still mostly "repeat a row" or "stack grids" shapes, though, and logic (`if`, `and`, `or`, comparisons) is almost absent.

## Next steps (for the R1 ranker)

- **Row format** (one JSON object per line):

  ```
  {"task": <training task id>, "ex": <index into train+test inputs>, "prog": <seed s-expr JSON, readable by seed::from_json>, "out": <grid>}
  ```

  The input is `train+test[ex].input` of `data/ARC-AGI/data/training/<task>.json`. There is one row per distinct (task, ex, out), and it holds the shortest program found for that output.
- For a ranker, group rows by task. For each (task, program), the program applied to the other inputs of the same task gives multi-example pseudo-tasks. That is cheap with `gpusynth_verify`'s eval path or a GPU pass.
- Diversity work still open:
  - Lower the weight of `repeat`; it is the root of 43% of rows.
  - Add a bool-producing bias, or seed `if`/`eq` templates, so that logic gets covered and `and`/`or` can be verified.
  - Add lambda primitives (map/filter/zipwith), the E5/L1 kernel.
  - Dedup across grids by program behaviour, not only by output.
  - The space saturates by about 1 minute (rate 10k/s → 4k/s), so more run time gives little. New primitives or lambdas are the lever.

## Reproduce

```
make -C native gpusynth gpusynth-verify
python3 -I native/gpu/synth/prep.py data/ARC-AGI/data/training <grids.bin> <names.json>
native/bin/gpusynth --grids <grids.bin> --names <names.json> --seconds 300 --mark 30 --write 100000000 --out <scratch>/v2-5m.jsonl
native/bin/gpusynth_verify --data data/ARC-AGI/data/training --n 10000 --jsonl <scratch>/v2-5m.jsonl [--only if,eq,lt]
```

Defaults are `--maxt 12 --mint 4 --dedup 1 --batch 262144`. The 5-minute run ran in the scope `arcagi-n6b-synth5m` (MemoryMax 12G, nice 19), with the GPU at 67-68 °C and the run using under 300 MB of VRAM.
