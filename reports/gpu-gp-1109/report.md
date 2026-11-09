# N3 GPU 遺傳式程式搜尋（gpgp）——同 GPU 時間下 GP／random／窮舉

← [夜跑看板](../../notes/rounds/gpu-night-1109/README.md)｜白話 [gp-白話](../../notes/rounds/gpu-night-1109/gp-白話.md)｜交接 [progress](progress.md)｜N2 雛形 [prototype](../native-cuda-1109/prototype.md)

## 問題

同一段 GPU 時間裡，遺傳式程式搜尋（GP）能不能在窮舉到不了的深度找到窮舉找不到的解？目的是改進 aos 的搜尋能力，不是衝解題率。

## 設計（摘要）

- `native/gpu/gp/gp_kernel.cu` 直接 `#include "../kernel.cu"`：原語與判解（`Verdict`）和 N2 窮舉同一份。
- 個體＝字母表索引序列（長 1..10）；預設 65536 個體、256 島；適應度 = 0.5·逐格相符 + 0.35·列聯表 colormap 相符 + 0.15·形狀 − 0.002·長度。菁英、環狀遷移、隨機移民、錦標賽、一點交配、四種突變。
- **判解**：train 全過 `Verdict`（exact，或尾端補一張 colormap）且 test 輸出合法；CPU 再以 arcsearch 原語確認並貪婪化簡，`depth` = 化簡後步數（不含尾端 colormap）。注意：這只保證 train 一致，**test 對不對要看 Python 驗證欄**。
- `--random`：同一取樣器、不做選擇（對照組）。`--synth`：植入長度 L 的隨機程式造題，且確認深度 < 4 全空間無解。
- 窮舉對照＝N2 `gpusearch --mode gpu --dedup 4 --prefix-cap 3000000 --depth 8 --stop-first`，同每題秒數。

## 族群大小調校（與 N2 長跑共用 GPU；題 6e19193c，15 秒）

| --pop | 功耗 | eval/s | 代數 |
|---|---|---|---|
| 65536 | 93 W | 1.02e7 | 2328 |
| 524288 | 125 W | 1.89e7 | 543 |
| 2097152（2048 島） | 114 W | 1.45e7 | 104 |

整夜長跑採 `--pop 524288`（顯存約 0.5 GB）。比較實驗用預設 65536（GP 與 random 相同）。

## 結果（自動製表 11-10 00:14；指令見下）

real-40＝主線未解題 training／evaluation 各 20（每題 20 秒）；synth-L*＝植入長度 L、深度<4 無解的合成題（每題 15 秒）。'C++ 解出'＝train 一致；真正答對看 Python test 欄。

### real

| 方法 | 題數 | C++ 解出 | 解深度分布 | Python train 全過 | Python test 全過 | 只有它解出 |
|---|---|---|---|---|---|---|
| gp | 40 | 1 | d7×1 | 1 | 0 | 1 1fad071e |
| random | 40 | 0 | — | 0 | 0 | 0  |
| exhaustive | 40 | 0 | — | 0 | 0 | 0  |

### synth-L5

| 方法 | 題數 | C++ 解出 | 解深度分布 | Python train 全過 | Python test 全過 | 只有它解出 |
|---|---|---|---|---|---|---|
| gp | 16 | 16 | d4×8, d5×6, d6×1, d8×1 | 16 | 16 | 0  |
| random | 16 | 12 | d4×11, d5×1 | 12 | 12 | 0  |
| exhaustive | 16 | 16 | d4×14, d5×2 | 16 | 16 | 0  |

### synth-L6

| 方法 | 題數 | C++ 解出 | 解深度分布 | Python train 全過 | Python test 全過 | 只有它解出 |
|---|---|---|---|---|---|---|
| gp | 19 | 18 | d4×13, d5×2, d6×2, d7×1 | 18 | 17 | 0  |
| random | 19 | 14 | d4×13, d5×1 | 14 | 13 | 0  |
| exhaustive | 19 | 18 | d4×17, d5×1 | 18 | 17 | 0  |

### synth-L7

| 方法 | 題數 | C++ 解出 | 解深度分布 | Python train 全過 | Python test 全過 | 只有它解出 |
|---|---|---|---|---|---|---|
| gp | 16 | 15 | d4×8, d5×4, d6×2, d7×1 | 15 | 12 | 0  |
| random | 16 | 11 | d4×5, d5×6 | 11 | 10 | 0  |
| exhaustive | 16 | 14 | d4×12, d5×2 | 14 | 12 | 0  |

## 結論（第 3 棒，11-10 00:2x）

**一句話：GP 沒有在窮舉到不了的深度找到任何「真的對」的解；它的 "solved" 大多是 train 擬合，在真題上幾乎全是過擬合。窮舉在速度與可信度上都勝，GP 只在合成題上小贏隨機對照。**

數字（統計腳本 `scratchpad/n3c/stats.py`，讀 `bench/*/*.jsonl`）：

| 題組 | 解題數（C++ train／Python test）GP · random · 窮舉 | 兩者都解時深度 GP 較長／相同／較短 | 解題中位秒數 GP · random · 窮舉 |
|---|---|---|---|
| real-40 | 1/0 · 0/0 · 0/0 | — | 3.6 · — · — |
| synth-L5 | 16/16 · 12/12 · 16/16 | 7／9／0 | 0.57 · 1.26 · 0.30 |
| synth-L6 | 18/17 · 14/13 · 18/17 | 4／14／0 | 0.59 · 0.77 · 0.45 |
| synth-L7 | 15/12 · 11/10 · 14/12 | 5／9／0 | 0.91 · 4.27 · 0.31 |

1. **解題數**：GP 與窮舉打平（test 對的題數 L5 16=16、L6 17=17、L7 12=12）。L7 兩邊各有一題獨得（GP：22eb0ac0-L7；窮舉：d037b0a7-L7，GP 在這題只 train 擬合、test 錯）。GP 明顯勝過無選擇的 random（L7 test 12 vs 10、中位快 4.7 倍），證明選擇壓力有用。
2. **解到的深度**：植入長度 5～7 的合成題，窮舉都在深度 4～5 找到等價短程式（合成題的「難度」被短等價解吃掉）。GP 的解從不比窮舉短，有 16 題更長——那不是「探得更深」，而是沒化簡乾淨的冗長程式（bloat）。表上的 d6～d8 不代表 GP 開出窮舉到不了的新深度。
3. **速度**：窮舉每秒評估約 6e7 候選，GP 約 9e5 個體×train（量綱不同，但差近兩個數量級）；解題中位時間窮舉 0.3～0.45 秒，GP 0.57～0.91 秒。窮舉跑完一層就能說「此深度無解」，GP 沒有這種保證。
4. **重點警訊——過擬合**：real-40 唯一的 GP 解 1fad071e（8 步）Python 重驗 train 過、test 錯。整夜 `arcagi-n3-gp` pass-1 前 232 題（00:22 時）C++ 判 7 題 solved，Python 重驗 **7 題 train 全過、test 只 1 題對**（a79310a0；錯的是 1fad071e、2013d3e2、239be575、25d8a9c8、aabf363d、d9fac9be，長 1～9 步）。即「GP solved」的 test 準確率約 1/7≈14%；合成題上也有 L6 1 題、L7 3 題 train-only。原因：適應度只看 train，長度懲罰 0.002／步太輕，GP 很會拼出「剛好吻合 2～3 組 train」的長鏈。

### 對照使用者方向的下一步

- **衡量搜樹速度**：本次以「同秒數、同原語」比，窮舉 1–2 數量級勝出；GP 值得用的地方只剩窮舉空間爆掉的深度（>6），但在那裡要先證明它解的是真題而非噪音。建議下一輪比較改報「test 對的題數 vs GPU 秒」曲線，不再報 C++ solved。
- **GP 當 aos 樹演化前身**：適應度要加泛化約束才可接到 aos——(a) **train 留一（leave-one-out）holdout**：train 對留出的那組也要對才算解；(b) **MDL 懲罰**：長度懲罰改為以 bit 計（程式長度＋參數）而非 0.002／步，並在判解時要求化簡後長度 ≤ 窮舉在同題已證無解深度＋小常數；(c) 解出後強制化簡到不可再刪（目前貪婪化簡留下 bloat）。
- 族群初始化可用窮舉淺層（d≤3）的高分前綴當種子，GP 只負責延伸，兩者分工而非競爭。

## 指令

```
make -C native gpugp
native/bin/gpgp --synth reports/gpu-gp-1109/synth/L$L --tasks reports/gpu-gp-1109/synth-sources.txt --synth-len $L --min-depth 4 --seed $L   # L=5,6,7
native/gpu/gp/bench.sh reports/gpu-gp-1109/real-40-paths.txt reports/gpu-gp-1109/bench/real 20
native/gpu/gp/bench.sh reports/gpu-gp-1109/synth/L$L-paths.txt reports/gpu-gp-1109/bench/synth-L$L 15 reports/gpu-gp-1109/synth/L$L
python3 native/gpu/gp/bench_table.py reports/gpu-gp-1109/bench/*
```

程式碼 commit：ab66b40（gpgp 原始碼）、a463e69（overnight GP_ARGS）、cfd176a（bench_table）。

