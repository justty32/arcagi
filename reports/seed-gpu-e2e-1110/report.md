# N5c：seed GPU 層接進真正的 seed 搜尋（`--gpu-seed`），端到端對照

## 白話

把上一棒（N5b）的 GPU 一階原語層接進真正的 seed 搜尋後，**整體沒有變快，反而變慢**：預算 1e6 時 GPU 版（門檻 2 萬候選）牆鐘 21.1 秒，CPU 原版 9.1 秒，慢 2.3 倍；預算 1e7 時 187.6 秒對 129.4 秒，慢 1.45 倍。把門檻提到 20 萬候選，1e6 打平、1e7 仍慢 1.25 倍。解集合則完全一致：兩個預算、三種模式、每次重跑，100 題的程式、train／test 對錯、節點數、到解節點都逐列相同。
瓶頸有兩個。第一是 Amdahl：GPU 能做的一階原語段雖然佔 66% 的節點，卻只佔 CPU 列舉時間的 26%；其餘 74% 是 map／filter／zipwith／fold 這些 lambda 類、`if` 與 library block。所以就算 GPU 不花時間，整體最多也只快約 1.35 倍。第二是搬運成本：每一題各自搜尋，不像 N5b 那樣 100 題一起跑，每層 GPU 候選只有幾萬到幾十萬個。每個 GPU 層要付約 27 ms 上傳值、約 14 ms 啟動和等待，而且每個拆解子問題都是新的列舉器，要把整個 bank 重傳一次。顯卡還同時被夜跑的 gpusearch／gpgp 佔滿。
**結論**：只搬一階原語不值得繼續最佳化。要整體加速，要嘛做 lambda kernel（瞄準那 74%），要嘛把 bank 常駐 GPU、多個子問題和多題批次合併 launch，才吃得到 N5b 量到的 16–30 倍吞吐。建議先做 lambda kernel 的可行性量測，看 BodyPool × 元素能不能變成定長，再決定。

## 做法（實作細節見 `progress.md`）

- 新 binary：`native/bin/arcbatch-gpuseed`，用 `make -C native gpuseed-e2e` 建置。它是 `src/main.cpp`（`-Dmain=arcsearch_main`）加上包裝 `native/gpu/seed/e2e_main.cpp`，再加列舉器副本 `native/gpu/seed/seed_enum_gpu.cpp`；`native/src/` 沒改。不帶 `--gpu-seed` 時與 `arcbatch` 相同。
- 每一層先在 host 端規劃所有「段」(op, comp)。支援的一階原語段，依 CPU 原本的順序（桶 a → 項 a → 桶 b → 項 b）給每個候選一個 64-bit 名次，交給 GPU 求值、算指紋，用 `atomicMin(名次)` 去重，所以勝者就是 CPU 會先遇到的那一個。回傳每個候選的狀態：SKIP（交換律跳過）、NODE（失敗或重複）、SURVIVOR。
- 接著 host 依原順序走一遍：不支援的段照舊由 CPU 跑；NODE 只批次累加節點數（預算檢查同 emit）；SURVIVOR 回 CPU 用真值重算一次再 offer，所以命中、near、seen 去重都和原版相同。分塊時每塊取連續的名次區間，搜尋走到哪才 launch 到哪。
- 已知差異：只有 `eval_steps`（只用於輸出加總）和秒數不同。64-bit 指紋理論上可能碰撞；`ARC_GPUSEED_VERIFY=1` 在 1e5、所有層都上 GPU 的條件下，逐一複查了 625 萬個 GPU 判定，0 錯。

## 1. 端到端對照（training 前 100 題，`--mode seed`，decomp，4 執行緒，三種模式交錯各跑 3 次，取中位數）

cpu＝`bin/arcbatch`；gpu＝`--gpu-seed`（`--gpu-min 20000`）；gpuhi＝`--gpu-seed --gpu-min 200000`。nodes／s＝總節點數 ÷ 牆鐘中位數。到解秒＝train 對各題 `seconds` 加總的中位數。

| 預算 | 模式 | 牆鐘秒 中位（範圍） | task 秒 中位 | 節點 | 節點／秒 | train 對 | test 對 | 到解秒 | 與 cpu 不同列數 |
|---|---|---|---|---|---|---|---|---|---|
| 1e6 | cpu | 9.1 (9.1..10.3) | 35.8 | 92,571,392 | 10.17M | 7 | 5 | 0.19 | 0 |
| 1e6 | gpu | 21.1 (21.1..23.6) | 83.0 | 92,571,392 | 4.38M | 7 | 5 | 0.70 | 0 |
| 1e6 | gpuhi | 9.1 (9.1..10.2) | 35.9 | 92,571,392 | 10.18M | 7 | 5 | 0.18 | 0 |
| 1e7 | cpu | 129.4 (126.2..141.5) | 510.0 | 895,292,707 | 6.92M | 10 | 7 | 1.87 | 0 |
| 1e7 | gpu | 187.6 (184.6..194.2) | 744.0 | 895,292,707 | 4.77M | 10 | 7 | 4.75 | 0 |
| 1e7 | gpuhi | 162.1 (161.6..165.8) | 641.8 | 895,292,707 | 5.52M | 10 | 7 | 2.62 | 0 |

整體加速（cpu 牆鐘 ÷ 該模式牆鐘）：1e6 時 gpu 0.43×、gpuhi 1.00×；1e7 時 gpu 0.69×、gpuhi 0.80×。
解集合：1e7 train 對的 10 題是 1e0a9b12、1fad071e、22eb0ac0、239be575、25d8a9c8、25ff71a9、27a28665、2dee498d、3c9b0459、445eab21；test 對的 7 題是 1e0a9b12、22eb0ac0、25d8a9c8、25ff71a9、27a28665、2dee498d、3c9b0459。三種模式完全相同（0 列不同，比對欄位為 program／train_ok／test_ok／nodes／nodes_to_first／near）。

## 2. 瓶頸（`--seed-prof`，1e6，一次跑，所有執行緒加總）

| | CPU 模式 | `--gpu-seed`（門檻 2 萬） |
|---|---|---|
| 列舉器總時間 | 30.8 s | 66.1 s |
| 支援的一階段 | 8.1 s（26%） | 18.5 s（其中 GPU launch＋wait 11.6 s） |
| 其他段（lambda 類、if、block） | 22.6 s（74%） | 24.9 s |
| 上傳 entry 到 GPU | – | 22.6 s |
| 支援段節點／全部節點 | 61.07M ／ 92.57M（66%） | 同左 |
| GPU 層數／候選／存活 | – | 836 ／ 37.2M ／ 2.42M |

Amdahl 上限：一階段時間若降到 0，整體只快 1／0.74 ≈ 1.35 倍。

## 重跑

```sh
make -C native gpuseed-e2e
ls data/ARC-AGI/data/training | sort | head -100 | sed 's/.json//' > train100.txt
echo '{"name":"base","budget":10000000,"decomp":true}' > cfg-10000000.jsonl
systemd-run --user --scope --unit=arcagi-n5c-x -p MemoryMax=12G nice -n 19 \
  native/bin/arcbatch-gpuseed --mode seed --tasks train100.txt --configs cfg-10000000.jsonl --threads 4 --gpu-seed [--gpu-min 200000] [--seed-prof] --out res.jsonl
uv run pytest -q tests/native
```
交錯 3 次的腳本和原始輸出在 scratchpad `/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n5c/`（`bench.sh`、`res-*.jsonl`、`wall.txt`）。用 `python3 -I reports/seed-gpu-e2e-1110/analyze.py <該夾>` 就能產生上表。

## 測試

`uv run pytest -q tests/native`：26 passed（新增 `tests/native/test_gpuseed_e2e.py` 4 個）。

## 未做

warp 協作 grid 雜湊（小層長尾）：端到端瓶頸在上傳和 Amdahl，不在 kernel 長尾，所以沒做。
