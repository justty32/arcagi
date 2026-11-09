# seed 列舉一層搬 GPU（N5b）：同層一致＋吞吐比

依 `reports/seed-forbid-1110/seed-gpu-可行性.md`「最小可驗的一步」。程式 `native/gpu/seed/`，binary `native/bin/gpuseed`（`make -C native gpuseed`），測試 `tests/native/test_gpuseed.py`。原始輸出：`run-L3.jsonl`、`run-L6.jsonl`（本夾）。

## 做法

- CPU 端就是真的 `seed::Enumerator`：`host.cpp` 直接 `#include "../../src/seed_enum.cpp"`（不改 `native/src/`），照 `Enumerator::run` 逐層跑（空 library、不分解、`task_consts(train 入+出)`、`out_type` 設成不存在的型別，命中不提早停）。
- 對第 L 層：CPU 已建好的大小 < L 的 bank → 轉成 GPU 定長值（int／bool／list[int] 用 int8 格／矩形 grid）；型別 unify 在 CPU 對「型別桶」做（呼叫原 `unify`／`resolve`，順序同 `choose`），產出 job＝(原語, 子桶 a, 子桶 b, 回傳型別)。
- GPU 一個 kernel 跑 100 題整層：每執行緒一個候選 → 交換律 seq 跳過（同 `emit`）→ 對每個 train 例求值（list／grid 結果是「視圖」，不物化）→ 結構雜湊 → 指紋 (型別, n 個值雜湊) → 每題一張開址表 atomicCAS 去重（表預載大小 < L 項目的指紋）→ 勝者回傳 (候選 id, 指紋)。
- 比對：每題、每層，GPU 新項目指紋集合 == CPU 該層新 entry 指紋集合（CPU 指紋由 CPU 求出的 V 值算），GPU 節點數 == CPU `nodes` 增量。

**GPU 支援的原語（20）**：add sub mul neg mod eq lt max min and or not len nth head last take drop reverse transpose。
**不支援（12，兩邊都排除，經 `set_exclude`）**：if cons append concat range repeat count sort map filter zipwith fold（lambda 類＋會產生不定長／非矩形值的）。library block 也不支援（本次空 library）。

## 1. 同層一致性（training 前 100 題）

| 層 | 節點 CPU=GPU | 新項目 CPU=GPU | 指紋集合不一致題數 | 節點數不一致題數 | 不支援而略過 |
|---|---:|---:|---:|---:|---:|
| 2 | 1,439 | 1,037 | 0 | 0 | 0 |
| 3 | 59,560 | 6,054 | 0 | 0 | 0 |
| 4 | 103,419 | 11,895 | 0 | 0 | 0 |
| 5 | 593,270 | 51,945 | 0 | 0 | 0 |
| 6 | 1,366,652 | 135,507 | 0 | 0 | 0 |

任務要求的 2–3 層全一致；多量的 4–6 層（同一套碼，bank 由 CPU 給到 L−1）也全一致。

## 2. 吞吐比（候選／秒，候選＝節點）

CPU＝真 Enumerator 逐層計時、4 執行緒（每執行緒 25 題，取最慢執行緒的牆鐘）；GPU＝RTX 5060 Ti，一次 launch 跑 100 題整層，kernel 時間取 20 次。

| 層 | 節點 | CPU 4 執行緒 | CPU 每執行緒 | GPU kernel（最佳／平均） | GPU 含重設表 | 比（kernel 平均 / CPU4） |
|---|---:|---:|---:|---:|---:|---:|
| 2 | 1.4k | 1.2e7 | 3.6e6 | 3.4e6 / 1.5e6 | 0.9e6 | 0.13× |
| 3 | 59.6k | 5.4e7 | 1.6e7 | 1.46e8 / 1.42e8 | 6.2e7 | 2.6× |
| 4 | 103k | 4.5e7 | 1.3e7 | 3.4e8 / 3.1e8 | 1.2e8 | 7.0× |
| 5 | 593k | 5.4e7 | 1.7e7 | 9.3e8 / 8.7e8 | 4.7e8 | 16× |
| 6 | 1.37M | 4.5e7 | 1.5e7 | 1.44e9 / 1.37e9 | 8.5e8 | 30× |

（2–3 層取自 `run-L3.jsonl`，4–6 層取自 `run-L6.jsonl`；兩檔 2–3 層數字幾乎相同。）上傳 bank 一次約 12–38 ms，不算進上表。顯存用量 ≤133 MB。

重跑：
```
make -C native gpuseed
cd native && ./bin/gpuseed --max-layer 3 --reps-cpu 3 --reps-gpu 20 > ../reports/seed-gpu-1110/run-L3.jsonl
cd native && ./bin/gpuseed --max-layer 6 --reps-cpu 3 --reps-gpu 20 > ../reports/seed-gpu-1110/run-L6.jsonl
```
（選項：`--data DIR --limit 100 --threads 4`；每行一個 JSON，`"task"` 行＝某題不一致或不支援。）

注意比法的偏差：CPU 數字包含 Enumerator 的全部成本（choose 遞迴、型別 unify、hash-cons 物化、勝者建 PP 樹）；GPU 只做生成＋求值＋雜湊＋去重，勝者不物化（只回 id＋指紋），型別 unify 在 host 先做（不計時）。所以比例是「這一段搬上去」的上限樣貌，不是整體搜尋加速。

## 白話

把 seed 搜尋「一層一層長程式」中的一層，原封不動搬到顯卡上：顯卡一次替 100 題同時試完這層所有組合，算出每個程式在範例上的輸出、丟掉跟以前重複的，留下新的。拿來跟原本 CPU 版逐題對帳，2 到 6 層、100 題、每一個新程式和每一個計數都對得上。速度上，層越大顯卡越划算：第 2、3 層組合太少（一千到六萬個），顯卡光啟動就吃掉時間，只比 4 核 CPU 快 2.6 倍（第 2 層甚至更慢）；到第 5、6 層（六十萬到一百多萬個）就快到 16–30 倍。但這只算到一階原語；seed 真正常用的 map／zip 這類帶小函式的原語還在 CPU，要整體大加速得把它們也搬上去（可行性報告的 Amdahl 警告仍成立）。

## 已知限制

- 小層（≤6 萬候選）kernel 時間卡在約 0.4 ms：一個執行緒算一整張 30×30 grid 的雜湊（transpose／reverse 等），長尾執行緒拖住整個 launch；可改 warp 協作雜湊。
- 指紋是 64-bit 雜湊，理論上有碰撞；本次 100 題×6 層集合完全相等，未見碰撞。
- 值佈局只支援 int8 格、矩形 grid；超出就整題標 `gpu_unsupported`（本次 0 題）。
