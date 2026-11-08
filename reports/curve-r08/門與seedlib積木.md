← 入口 [curve-r08/README](README.md)

## 門：舊門（MDL /4）跟新門（MDL /1）各擋掉哪些題

| 曲線 | 舊門（gate4-0bea07d）擋掉的 | 新門擋掉的 |
|---|---|---|
| pool | L `beb8660c`（留一，pass 0–2）、L `d10ecb37`（MDL，全程） | L `beb8660c`（留一，全程） |
| pool-rand32 | L `beb8660c`（留一）、L `d10ecb37`（MDL）、P `3c9b0459`（留一，pass 1）、P `7b7f7511`（MDL，test 錯，擋得對） | L `beb8660c`（留一）、P `3c9b0459`（留一，pass 1）、P `7b7f7511`（留一，pass 1–8，test 錯，擋得對） |
| pool-foot32 | — | L `beb8660c`（留一，pass 0–2）、P `b1948b0a`、`c8f0f002`（留一，pass 0–1） |

- 被擋的 L 題 test 其實都對（beb8660c、d10ecb37）：門是保守的。新門下 `false_pos` 全 0。
- `pool-noG1` 不學，門只影響哪些程式進 G1，所以 pool-noG1 的解題數不受門影響；新快照照樣重跑了一次（sha `4d33bbce43c8`）。

## seedlib 積木（來源 P／L）

| 樹 | 名稱 | body | 簽名 | 省量 | 來源 | 主題 | L16 用次 | 共用題數 |
|---|---|---|---|---|---|---|---|---|
| dec-g1 | `g1_0177e4faae` | `["lam", 1, ["sort", ["$0"]]]` | `(list[a]) -> list[a]` | 3.0 | L | — | 0 | 0 |
| dec-g1 | `g1_f72643d574` | `["map", ["lam", 1, ["sort", ["$0"]]], ["$h0"]]` | `(list[list[a]]) -> list[list[a]]` | 2.0 | L | — | 16 | 2 |
| pool-rand32 | `g1_0652240849` | `["transpose", ["$in"]]` | `list[list[int]]` | 2.0 | P+L | geometry.flip_rot | 0 | 1 |
| pool-foot32 | `g1_2ff25d9c21` | `["map", ["lam", 1, ["append", ["$0"], ["reverse", ["$0"]]]], ["$in"]]` | `list[list[int]]` | 7.0 | P | scale_tile.mirror_tile | 0 | 5 |
| pool-foot32 | `g1_019b408846` | `["reverse", ["$in"]]` | `list[list[int]]` | 6.0 | P+L | scale_tile.mirror_tile | 8 | 4 |
| pool-foot32 | `g1_0652240849` | `["transpose", ["$in"]]` | `list[list[int]]` | 6.0 | P+L | geometry.flip_rot, geometry.transpose | 0 | 6 |
| pool-foot32 | `g1_6b6baf343b` | `["transpose", ["reverse", ["blk", "g1_0652240849"]]]` | `list[list[int]]` | 6.0 | P | geometry.flip_rot | 0 | 3 |
| pool-foot32 | `g1_e6ba9d8a6f` | `["reverse", ["blk", "g1_0652240849"]]` | `list[list[int]]` | 6.0 | P | geometry.flip_rot | 0 | 1 |
| pool-foot32 | `g1_996048a4bc` | `["append", ["blk", "g1_2ff25d9c21"], ["reverse", ["blk", "g1_2ff25d9c21"]]]` | `list[list[int]]` | 4.0 | P | scale_tile.mirror_tile | 0 | 3 |
| pool-foot32 | `g1_0392d6a5b1` | `["append", ["$in"], ["blk", "g1_019b408846"]]` | `list[list[int]]` | 3.0 | P | scale_tile.mirror_tile | 0 | 2 |
| pool-foot32 | `g1_ab1fc6264d` | `["reverse", ["blk", "g1_6b6baf343b"]]` | `list[list[int]]` | 2.0 | P | geometry.flip_rot | 0 | 2 |
| pool-g4/seed1 | `g1_82c739c4e2` | `["repeat", 3, ["$h0"]]` | `(a) -> list[a]` | 5.0 | L-near | — | 0 | 0 |
| pool-g4/seed1 | `g1_2119d64b73` | `["repeat", 3, ["repeat", ["$h0"], ["$h1"]]]` | `(int, a) -> list[list[a]]` | 1.0 | L-near | — | 0 | 0 |
| pool-g4/seed1 | `g1_1a40b22956` | `["repeat", 4, ["$h0"]]` | `(a) -> list[a]` | 1.0 | L-near | — | 0 | 0 |
| pool-g4/seed1 | `g1_0652240849` | `["transpose", ["$in"]]` | `list[list[int]]` | 2.0 | L | — | 0 | 0 |
| pool-g4/seed1 | `g1_d417bb28c8` | `["sort", ["transpose", ["$h0"]]]` | `(list[list[a]]) -> list[list[a]]` | 1.0 | L-near | — | 0 | 0 |

- `pool`（主題 P32）一個積木都沒長。`pool-g4` seed 2、3 的積木跟 seed 1 相同。來源 `L-near`：冷啟動時從未解 L16 題的最佳近解抽出的模板（D-r7-10）。

庫放在 `aos/seedlib/r08-<tree>/blocks.json`；每條曲線出生過的積木全部記在 `reports/curve-r08/<tree>/blocks_born.json`。


