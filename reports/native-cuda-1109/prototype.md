# CUDA 候選程式評估雛形（gpusearch，11-09 夜）

任務：把 arcbatch 的候選程式評估搬一部分上 GPU，跟 CPU 在**同一組題、同一程式空間**比吞吐、結果要一致（來源：`notes/rounds/gpu-night-1109/00-REQUEST.md` 第 2 條）。程式碼 commit **`1ca9a6f`**。

## 一句話結論

GPU 版在同一程式空間比 CPU 版（arcsearch 自己的原語，6 執行緒）快 **約 45 倍（深度 3）到 105 倍（深度 4）**，200＋12 題的解集合**逐題完全一致**，抽 399 支 GPU 找到的程式交 Python `arcagi.dsl.program` 跑，train **399/399 全對**。

## 設計

- **程式空間**（`native/gpu/space.hpp`）：每題一份字母表，由完全帶參數的格子步驟組成：D4 七種、`upscale`／`tile`／`downscale`（倍率 1..3）、`mirror_tile`、`crop_bbox`、`gravity`、`fill_enclosed`、`split_overlay`（2 軸×5 運算）、`self_tile`、單對 `colormap [[a,b]]`（a ∈ 題目輸入色∪{10}，b ∈ train 輸出色∪{0}）。字母表大小每題 59～125。程式＝長度 1..k 的任意步驟序列。
- **判解**跟 arcsearch `evaluate()` 一樣：train 全部完全相同（且 test 輸出合法）＝`exact`；否則形狀全對時配一張終端 colormap（`fit_colormap` 的規則，含 test 中 >9 色必須有對映）＝`colormap`。任何一步失敗或越界（>30）就丟。
- **GPU**（`native/gpu/kernel.cu`）：所有原語逐行照 `native/src`（grid.cpp、prims_base.cpp、prims_more.cpp、learners.cpp）寫成 device 函式。兩種核心：
  - `k_flat`：一執行緒＝一支程式，每個 pair 從頭跑；
  - `k_shared`（預設）：一執行緒＝一個長度 k−1 的前綴，先在 pair 0 算一次前綴狀態，再對它試全部 A 個最後一步；只有過了 pair 0 的才去跑其它 pair。
- **CPU 對照**（`native/gpu/driver.cpp` 的 `CpuSide`）：同一字母表、同一判解，但用 **arcsearch 自己的 `apply_step`／`fit_colormap`**，DFS 每節點只套一步（共用前綴，就是 arcsearch 的成本模型），6 執行緒。兩邊都把每支解編成同一個索引，逐題比**整個解集合**（不只解數）。
- **去重模式**（`--dedup P`，只給 GPU，用在整夜）：深度 ≤P 照暴力跑；更深的程式＝「唯一的長度 P 前綴」×任意後綴。唯一前綴用 CPU BFS 求：在全部 train＋test 輸入上狀態完全相同的前綴只留第一個（觀測等價）。這跟 arcsearch 的 `seen` 同一個想法，所以不算在「同一程式空間」的比較裡。
- 吞吐定義：候選數／秒，候選數＝程式空間大小 Σ A^d（兩邊相同；CPU 對失敗前綴的剪枝算它自己的省工）。

## 數字（GPU 與 LM Studio 的 gemma-4-e4b 共用，量測時顯卡已被佔用 86～92%）

| 題組 | 深度 | 空間（候選） | GPU 候選／秒 | CPU 候選／秒（6 緒） | 比值 | 解集合一致 |
|---|---|---|---|---|---|---|
| 200 題（training、evaluation 各 100，每 4 題取 1） | ≤3 | 1.55e8 | 6.89e7（k_shared） | 1.55e6 | **44.5×** | 200/200 |
| 同上 | ≤3 | 1.55e8 | 7.57e7（k_flat） | 1.55e6 | 48.9× | 200/200 |
| 12 題 training（字母表 ≤75） | ≤4 | 2.01e8 | 3.01e8（k_shared） | 2.85e6 | **105×** | 12/12 |
| 同上 | ≤4 | 2.01e8 | 1.37e8（k_flat） | 2.85e6 | 48× | 12/12 |

- 深度 3 每題空間小（≤2M），GPU 時間被啟動開銷主導，所以比值較低；深度越深 k_shared 越占優。
- 去重模式（GPU only）：深度 5（P=3）evaluation 6 題每題 0.1～6.5 秒；深度 6（P=4）3 題每題 0.3～31 秒，峰值 9.2e8 候選／秒。去重把等價前綴大量砍掉（例：59^2=3481 個長度 2 前綴只剩 695 個）。
- 顯存：gpusearch 一個程序約 512 MiB。

原始 JSONL：`reports/native-cuda-1109/bench/`（`d3-both-200tasks-*.jsonl`、`d4-both-12tasks-*.jsonl`、`d5-dedup3-6tasks.jsonl`、`d6-dedup4-3tasks.jsonl`）。`*-flat.jsonl` 兩檔是 k_flat 重構前（同邏輯，未抽 `Verdict`）跑的。

## 一致性核對

1. **GPU 與 CPU 解集合**：上表 212 題全部一致（每深度解數相同，且解索引集合相同）。
2. **Python 重驗**：`bench/samples-gpu.jsonl`（200 題深度 3＋12 題深度 4，每題附最多 20 支平均抽樣的解）交 `native/tools/gpu_verify.py`，用 `arcagi.dsl.program.run`（在題目背景色 context 下，跟 hybrid 入口重驗方式一樣）：**最佳程式 19/19、抽樣 380/380 train 全對**；最佳程式 test 對 18/19（25d8a9c8 是 `tile`＋`downscale`＋7 列 colormap 的過擬合，C++ 與 Python 對 test 判斷一致）。結果檔 `bench/samples-verify.jsonl`。
3. **既有測試**：`pytest tests/native` 17 passed（原 15＋新 `test_gpusearch.py` 2 個：GPU==CPU 解集合、Python train 重驗，k_shared／k_flat 各一）。

## S1 `forbid`

**沒做**，因為不相依：`forbid` 是 seed（空樹）語言的 AST 樣式剪枝（`--mode seed`、`seed_enum.cpp`），這個 GPU 雛形走的是格子步驟程式空間（arcsearch 那條）。請求信說 r10 才接，留給下一輪 S1。

## 整夜長跑

`native/gpu/overnight.sh`（截止 11-10 06:00，06:00 前後自動寫 `reports/native-cuda-1109/overnight-summary.md`，被 TERM 打斷也寫）：

- A 段：training＋evaluation 全部 800 題，深度 ≤5（去重 P=3），每題上限 120 秒，找到第一層有解就停。
- B 段：A 段沒 train 解、且主線未解（training 用 gated-r07 的 147 題、evaluation 用 gated-r08 的 56 題，清單在本目錄 `mainline-solved-*.txt`）的題，深度 ≤6（P=4），每題 600 秒。
- C 段：B 段仍無解的題，深度 7（P=4，跑不完就是部分覆蓋），每題 900 秒，跑到截止。
- 彙總會把每支找到的程式交 Python 重驗 train／test，列出「主線未解、test 對」的新題。找到的解只寫報告，不進 `aos/blocks/`。

啟動方式（systemd 單元 `arcagi-n2-overnight`）：

```sh
cp native/bin/gpusearch native/bin/gpusearch-overnight   # 跑的期間可重建 gpusearch
END=$(( $(date -d '2026-11-10 06:07' +%s) - $(date +%s) ))
BIN=$PWD/native/bin/gpusearch-overnight nohup systemd-run --user --scope --unit=arcagi-n2-overnight \
  -p MemoryMax=16G nice -n 19 timeout --signal=TERM --kill-after=60 $END \
  native/gpu/overnight.sh $PWD/reports/native-cuda-1109/overnight "2026-11-10 06:00" &
```

日誌：`reports/native-cuda-1109/overnight/run.log`；每題結果 `overnight/phase-{A,B,C}.jsonl`。

## 可重跑指令

```sh
make -C native gpu                                     # nvcc 13.4（/opt/cuda），產生 native/bin/gpusearch
# 同空間 GPU vs CPU（深度 3，200 題）
nice -n 19 native/bin/gpusearch --tasks reports/native-cuda-1109/bench/tasks-200.txt \
  --depth 3 --mode both --out /tmp/d3.jsonl
# 深度 4，12 題
nice -n 19 native/bin/gpusearch --tasks reports/native-cuda-1109/bench/tasks-d4-12.txt \
  --data-dir data/ARC-AGI/data/training --depth 4 --mode both --out /tmp/d4.jsonl
# 抽樣程式交 Python 重驗
native/bin/gpusearch --tasks reports/native-cuda-1109/bench/tasks-200.txt --depth 3 --mode gpu --samples 20 --out /tmp/s.jsonl
uv run --no-sync python native/tools/gpu_verify.py /tmp/s.jsonl | tail -1
uv run --no-sync pytest -q tests/native
```

## 下一步

- GPU 上直接做去重（狀態雜湊表），省掉 CPU BFS，前綴可做到 P=5，深度 7～8 才實際可行。
- 把 arcsearch 剩下的原語（物件類、cells 類、`x_*`）搬上 GPU，空間才跟正式 arcbatch 對齊；也可直接當 arcsearch 的「深度 k 葉層」加速器。
- 使用者方向（「GPU 遺傳符號回歸／大批候選程式評估」）：這個評估核心就是遺傳搜尋需要的適應度函式——下一步可以讓族群在 GPU 上突變／交配程式，每代幾億支一起評分；小網路當排序器／剪枝器排在之後。
- 過擬合：終端 colormap 會配出多列的表（如 25d8a9c8），整夜結果要配 arcbatch 的 support gate 再看。
