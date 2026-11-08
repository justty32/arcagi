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

（掃描進行中，結果補在下一個 commit。）

重跑：`uv run python -m arcagi.hammer.scan <root> --kind gate|route --work DIR [--write] [--probe N] [--dry]`。
