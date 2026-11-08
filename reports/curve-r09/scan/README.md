第九輪 B 線：`hammer/scan.py`（layer-2，意見 6「審查被暴力搜」）的第一次掃描。判準照 [03 §4 提案 3、4](../../../notes/rounds/r09/03-設計.md)，寫在 `scan.py` docstring，跑之前寫死。程式只讀 taskset 的 `learn`／`P48`；短曲線用 `epoch.run_epoch(..., holdout=False)`，樹的 truth 檔 H8／H24 是空清單。

## 設定

- 被掃的樹：scratch 根（`init_root`＋4 epoch，L16＋P48 的 75% 子集 seed 1，A 線 `run_epoch` 的 commit 前工作版，2026-11-08 19:05），不是活樹 `ws/hammer/`。ledger 與 ops 的寫入也只寫這個 scratch 根，示範 `--write` 的列形狀；要對活樹跑由隊長下 `python -m arcagi.hammer.scan ~/code/playground-arc1/ws/hammer --kind gate --write`。
- 短曲線：3 CRN seed（P48 子集 `pool.subset(P, seed, 0.75)`，L16 全）× 4 epoch，base 與變體同 seed；一條 4 epoch 曲線約 2.4 秒。
- 判決：`sha1(task_id+"r09AB")` 末位偶數＝A 折。A 折（三 seed 合計、末 epoch）0 掉題且多解、或同題數且 Σnodes_to_first 降 ≥5% → 選中；B 折折外也 0 掉題且多解 ≥1 或降 ≥5% → 接受。

## gate：gate_g1 鄰域 19 個變體

| 項 | 結果 |
|---|---|
| 變體 | 11 個單因子（`mdl_div` 0.5／2、`loo_frac` 0.1／0.5、`lib_cap` 8／32、`retire_after` 1／3、`k` 1／4、`max_holes` 1）＋8 個雙因子 |
| 離線重放（0 次 arcbatch）分群 | **1 群**：19 個變體產出的積木集 `blocks_sha` 全等於 base（`36f214181d24`） |
| 跑短曲線的代表變體 | 積木集有變的 0 個；另用 `--probe 4` 抽 4 個離線 Δ0 的變體真跑，驗去重是否對：4 個在 A、B 兩折都 0 掉題、0 多解、Σnodes_to_first 一模一樣（A 399,227、B 68,576） |
| 接受 | **0**；19 筆 ledger（`kind:layer2 layer:2 by:gate-scan`，`accepted:false`） |

- 為什麼全 Δ0：這棵樹的 G1 進料每 epoch 11～14 支程式，都很短，`mdl_div` 0.5～2 都過；`k`、`max_holes` 改了也挑出同樣的前 m 個詞；`loo_frac`／`loo_min_pairs` 離線看不到（沿用已存的 LOO 判決），`lib_cap`／`retire_after` 在 r09 的 ops 引擎裡不進 `sleep_ops`。跟 02 §9 M3 的預期「gate-scan 多數變體 Δ0」一致。
- 逐變體明細在 [gate.json](gate.json)。

## route：路由表鄰域

| 項 | 結果 |
|---|---|
| 鄰域 | 6 條 live route 列 × （priority ±1、換成另外 3 個 arm）＝30 個變體 |
| 被掃的樹 4 epoch 內出現的停滯狀態 | 只有 `ok`（base 取 `rt_sleep`） |
| 離線分群（按每個已出現狀態取到的 arm） | 4 群；與 base 不同的 3 群各跑一個代表（3 seed × 4 epoch，牆鐘 3 分 13 秒，`rt_vsplit` 那群走 Python 慢道） |
| 接受 | **1**：`route_ok_rt_sleep` 的 arm 改 `rt_vsplit`（ok 狀態改走縱拆）。A 折 0 掉題、Σnodes_to_first 降 14.4%；B 折折外 0 掉題、**多解 6 題**（三 seed 合計）、降 32.8% |
| 未接受 | ok→`rt_pool`：A 多解 1 但 B 節點 +98%、無多解；ok→`rt_gatescan`：兩折完全不變 |
| ledger | 30 筆 `layer:2 by:gate-scan`（接受者 1 筆帶新列 `route_ok_rt_sleep_scan3` live、舊列 dormant 並記 `tried_env_hashes`） |

- **要分開標**：接受的這條，B 折多解的題來自 `rt_vsplit` 慢道跑的 `decomp_halves`／`decomp_nest`（`by:agent-r08`，r08 手寫拆法）被樹判升 live（變體樹 seed 1：`decomp_halves` 新解 3c9b0459、496994bd、ce4f8723，`decomp_nest` 新解 3c9b0459）。照 03 §1 隊長改動 2，這算「手寫拆法經樹判升」，不是樹自己長出的拆法；它可以算 M2(b)（route 列被 layer-2 接受、B 折折外 0 掉題並多解），但不能算 M2(a)。
- 這次只在 scratch 根上做（`--write` 寫的是 scratch 根的 ops／ledger）。要讓活樹吃到，由隊長對 `ws/hammer/` 跑 `scan --kind route --write`，或把這條變體當 `add-op` 交樹判。
- 逐變體明細在 [route.json](route.json)。

重跑：`uv run python -m arcagi.hammer.scan <root> --kind gate|route --work DIR [--write] [--probe N] [--dry]`。
