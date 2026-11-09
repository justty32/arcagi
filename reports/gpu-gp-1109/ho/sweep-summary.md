# gpgp-ho MDL λ 掃描（n3e）

狀態：TERM。每格＝各 seed 平均（最小–最大）；`--simplify min`、無 holdout、每題 20 s；real-40 預設 pop，on40 pop 524288。

| 題組 | λ | seeds（完整/有資料） | 跑完題數 | train solved | Python test 對 | 假 solved 比例 | 中位長度 |
|---|---|---|---|---|---|---|---|
| on40 | 0 | 3/3 | 41 (41–41) | 6.3 (5–8) | 1 (1–1) | 84% (80%–88%) | 4.5 (4–5.5) |
| on40 | 0.003 | 3/3 | 41 (41–41) | 5.7 (5–6) | 1 (1–1) | 82% (80%–83%) | 4.2 (4–4.5) |
| on40 | 0.006 | 3/3 | 41 (41–41) | 3.7 (3–4) | 0.7 (0–1) | 83% (75%–100%) | 2.7 (2–3) |
| on40 | 0.01 | 2/2 | 41 (41–41) | 3.5 (3–4) | 0.5 (0–1) | 88% (75%–100%) | 2.5 (2–3) |
| real | 0 | 3/3 | 40 (40–40) | 1 (1–1) | 0 (0–0) | 100% (100%–100%) | 7.7 (7–9) |
| real | 0.003 | 3/3 | 40 (40–40) | 0.3 (0–1) | 0 (0–0) | 100% (100%–100%) | 7 (7–7) |
| real | 0.006 | 3/3 | 40 (40–40) | 0.3 (0–1) | 0 (0–0) | 100% (100%–100%) | 7 (7–7) |
| real | 0.01 | 2/3 | 31 (13–40) | 0 (0–0) | 0 (0–0) | — | — |

## 各 run 明細（solved / test 對）

- on40 λ=0 s1: solved 2013d3e2,25d8a9c8,a79310a0,aabf363d,d9fac9be,f8ff0b80；test 對 a79310a0
- on40 λ=0 s2: solved 2013d3e2,25d8a9c8,a79310a0,aabf363d,f8ff0b80；test 對 a79310a0
- on40 λ=0 s3: solved 1fad071e,2013d3e2,239be575,25d8a9c8,a79310a0,aabf363d,d9fac9be,f8ff0b80；test 對 a79310a0
- on40 λ=0.003 s1: solved 2013d3e2,239be575,25d8a9c8,a79310a0,aabf363d,d9fac9be；test 對 a79310a0
- on40 λ=0.003 s2: solved 2013d3e2,25d8a9c8,a79310a0,aabf363d,f8ff0b80；test 對 a79310a0
- on40 λ=0.003 s3: solved 2013d3e2,25d8a9c8,a79310a0,aabf363d,d9fac9be,f8ff0b80；test 對 a79310a0
- on40 λ=0.006 s1: solved 2013d3e2,25d8a9c8,aabf363d；test 對 —
- on40 λ=0.006 s2: solved 2013d3e2,25d8a9c8,a79310a0,aabf363d；test 對 a79310a0
- on40 λ=0.006 s3: solved 2013d3e2,25d8a9c8,a79310a0,aabf363d；test 對 a79310a0
- on40 λ=0.01 s1: solved 2013d3e2,25d8a9c8,aabf363d；test 對 —
- on40 λ=0.01 s2: solved 2013d3e2,25d8a9c8,a79310a0,aabf363d；test 對 a79310a0
- real λ=0 s1: solved 1fad071e；test 對 —
- real λ=0 s2: solved 1fad071e；test 對 —
- real λ=0 s3: solved 1fad071e；test 對 —
- real λ=0.003 s1: solved —；test 對 —
- real λ=0.003 s2: solved —；test 對 —
- real λ=0.003 s3: solved 1fad071e；test 對 —
- real λ=0.006 s1: solved —；test 對 —
- real λ=0.006 s2: solved —；test 對 —
- real λ=0.006 s3: solved 1fad071e；test 對 —
- real λ=0.01 s1: solved —；test 對 —
- real λ=0.01 s2: solved —；test 對 —
- real λ=0.01 s3（未完）: solved —；test 對 —

SWEEPDONE
