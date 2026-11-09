# N5d／B1：seed GPU 層的裝置 context 常駐、子題共用，`--gpu-seed` 端到端對照

## 白話

把 GPU seed 層的「搬運」修掉了：以前每個拆解子問題都新開一條 CUDA stream、重新配置顯存再整包上傳（1e6 共 1,253 次，光開 context 就約 25.6 秒〔4 執行緒加總〕），現在每個執行緒只開一次（共 4 次），之後的子問題都沿用同一份顯存、雜湊表和 pinned 暫存區，上傳只傳新進 bank 的增量。上傳加總從 49.7 秒降到 10.1 秒（−80%）。**但牆鐘沒有變快**：1e6、`--gpu-min 0` 時 b1 56.4 秒、原 gpu 54.2 秒、CPU 10.2 秒。省下的時間全部變成「等 GPU 回來」（gpu_s 113.6→166.0 秒）。真正的瓶頸是每一層都要和 GPU 來回一次：1e6 共 6,230 層，每層約 27 ms。這段時間 GPU 被其他夜跑（gpufill、gpgp、gpuprofile）佔滿 100%，我們每次小 launch 都要排隊等輪到。只要每層還要同步一次，搬運再省也追不上 CPU。解集合完全一致（0 列不同）。
**E8 判讀：停手。** 1e6 b1 牆鐘 56.4 s，大於 CPU 的 10.2 s，第一條（≤ cpu）就不過。照 E8，`--gpu-seed` 預設凍結在 `--gpu-min 200000`；b1hi（b1＋`--gpu-min 200000`）10.0 s，和 CPU 打平。

## 做法

- 新檔 `native/gpu/seed/b1_kernel.cu`：複製 `e2e_kernel.cu` 再改，介面（`e2e.hpp`）不變，所以 host 端 `seed_enum_gpu.o`、`e2e_main.o`、`main.o` 和 `arcbatch-gpuseed` 共用同一份物件，只換 kernel 物件。建置用 `make -C native gpuseed-b1`，產出 `native/bin/arcbatch-gpuseed-b1`；既有的 `arcbatch-gpuseed` 沒動。
  1. **常駐、共用池**：`e2e_destroy()` 不再釋放，而是把 context 放回 thread_local 池；下一個 Enumerator（同題的下一個拆解子問題，或下一題）直接拿來用，只把各緩衝的已用長度歸零，容量、stream、表、pinned 暫存都保留。表縮小時不重配置，只用實體陣列的前段。
  2. **pinned 暫存**：所有 H2D 先 memcpy 到每個 context 的 pinned 區，再做真正的非同步拷貝；status 的 D2H 進 pinned 區。
  3. **合批**：清表從兩個 memset 改成一個 kernel；每層第一次 eval 時把「插入既有指紋」併進同一個 launch（兩者都用 atomicMin，既有指紋的名次是 0，順序不影響結果）。每層固定 3 個 kernel（clear／eval／resolve）、1 次同步。
- 沒做的部分：同題不同子問題的 bank「內容」不跨子問題重用，每個子問題仍上傳自己的 bank 增量。原因是 bank 在 CPU 端本來就逐子問題重建，而且同步延遲才是瓶頸，重用內容也救不回牆鐘。

## 1. 端到端對照（training 前 100 題，`--mode seed`，decomp，4 執行緒，四種模式交錯各 3 次，取中位數）

cpu＝`bin/arcbatch`；gpu＝`arcbatch-gpuseed --gpu-seed --gpu-min 0`；b1＝`arcbatch-gpuseed-b1 --gpu-seed --gpu-min 0`；b1hi＝b1 加 `--gpu-min 200000`。量測期間 GPU 使用率一直是 100%（其他 arcagi-* 夜跑），溫度 64–68°C。

| 預算 | 模式 | 牆鐘秒 中位（範圍） | task 秒 中位 | 節點 | 節點／秒 | train 對 | test 對 | 與 cpu 不同列數 |
|---|---|---|---|---|---|---|---|---|
| 1e6 | cpu | 10.2 (10.0..10.2) | 40.2 | 92,571,392 | 9.10M | 7 | 5 | 0 |
| 1e6 | gpu | 54.2 (34.9..55.4) | 214.7 | 92,571,392 | 1.71M | 7 | 5 | 0 |
| 1e6 | b1 | 56.4 (44.3..57.0) | 222.1 | 92,571,392 | 1.64M | 7 | 5 | 0 |
| 1e6 | b1hi | 10.0 (9.5..11.3) | 39.6 | 92,571,392 | 9.24M | 7 | 5 | 0 |
| 1e7 | 全部 | 長跑中（見下） | | | | | | |

整體加速（cpu ÷ 該模式）：1e6 時 gpu 0.19×、b1 0.18×、b1hi 1.02×。

**1e7 還在跑**：單元 `arcagi-n5d-bench`（cpu／gpu／b1／b1hi 各 3 次，之後 gpu、b1 各跑一次 `--seed-prof`，跑完會寫出 `DONE`）。補表的指令是 `python3 -I reports/seed-gpu-b1-1110/analyze.py /tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n5d`。1e6 已經不過 E8 第一條，所以 1e7 的結果不影響判讀。

## 2. 上傳與 launch 前後對照（1e6、`--gpu-min 0`、`--seed-prof` 單次，4 執行緒加總）

| | 原 gpu | b1 |
|---|---|---|
| context 建立（stream＋配置） | 1,253 次（≈25.6 s，N5d 前置 debug 量測） | **4 次**（另有 1,249 次重用） |
| 上傳段 sync_s（含 host 轉換、建立 context） | 49.7 s | **10.1 s** |
| 其中 H2D 排入（b1 計數） | – | 37,378 次，3.68 GB，1.26 s |
| 每層 stream 操作 | 3 kernel＋2 memset＋jobs H2D＋D2H＋約 5 次 append H2D，另有 cudaMallocAsync／free 和擴容拷貝 | 3 kernel＋jobs H2D＋D2H＋append H2D；共 62,650 次操作、18,690 次 kernel、243 次 device malloc |
| GPU 層數／chunk | 6,230／6,230 | 6,230／6,230 |
| launch＋等待 gpu_s | 113.6 s | 166.0 s |
| 列舉器總時間 run_s | 192.5 s | 207.9 s |
| 顯存峰值 | 201 MB | 549 MB（池留住最大容量；上限 2.4 GB） |

讀法：搬運成本（上傳 −39.6 s、context 建立 −25 s）確實消失了，但等 GPU 的時間（每層一次同步）多了 52 s，總和打平。每個執行緒每層要等約 27 ms，比小層本身的計算時間大幾個數量級，延遲主要來自 GPU 被其他程序佔滿時的排隊。要吃到 N5b 量到的吞吐量，必須讓「一次同步」對應很多層或很多子題的工作（跨題批次、讓 GPU 跑整段搜尋），不是單層 offload 再微調可以做到的。

## 正確性

- 1e5、train100、`--gpu-min 0`、`ARC_GPUSEED_VERIFY=1`：逐一複查 6,251,811 個 GPU 判定，0 錯；和 `arcbatch` 比 0 列不同。
- 1e6 三種 GPU 模式 × 3 次：和 cpu 比 0 列不同（比對欄位為 program／train_ok／test_ok／nodes／nodes_to_first／near）。
- `uv run pytest -q tests/native`：29 passed，其中新增的 `tests/native/test_gpuseed_b1.py` 3 個：強制全上 GPU 的結果和 arcbatch 相同且 context 只建 ≤4 次、verify、CPU 模式。

## 重跑

```sh
make -C native gpuseed-b1
bash /tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n5d/bench.sh   # 交錯 1e6→1e7，結果在同一資料夾
python3 -I reports/seed-gpu-b1-1110/analyze.py /tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n5d
```
