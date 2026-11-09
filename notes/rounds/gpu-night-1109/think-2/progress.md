# think-2 進度（交接用）

← [代定清單](代定清單.md)｜[夜跑看板](../README.md)

狀態：**PARTIAL**（隊長 context 過 30%，主 session 指示換手）。做到 02b（審）為止。

## 已完成

| 段 | 檔 | 說明 |
|---|---|---|
| 01a 蒐集 | [01a-蒐集-sol.md](01a-蒐集-sol.md) | codex gpt-6.1-sol 唯讀，Q1～Q10，33 KB |
| 01 簡報 | [01-簡報.md](01-簡報.md) | 隊長寫；fable 只讀這份 |
| 02 規劃 | [02-規劃-fable.md](02-規劃-fable.md) | fable，20 KB，5 塊：1 往返工具 → 2 快撥＋雜訊尺＋兩守門 → 3 開放成本帳＋逐層分功勞 → 4 整棵樹 GA → 5 Janet |
| 02b 審 | [02b-Argon審.md](02b-Argon審.md) | agy Gemini 4 Argon (High)，plan 模式，全文貼進提示 |
| 代定 | [代定清單.md](代定清單.md) | D1～D10；Argon (B) 提案採不採納**尚未記**（下一棒做） |

## 關鍵事實（下一棒不用重查）

- 活樹 `/home/lorkhan/code/playground-arc1/ws/hammer/`：97 檔、無 symlink／二進位；定義＝`_metainfo.json`、`frozen.json`、`ops.jsonl`（21 列，定義欄與狀態欄混列）、`nodes/{7 種}/_metainfo.json`、`truth/{train/taskset.json,cal/ids.json}`；`ops/<id>/` 是 14 個 comb／decomp 投影。
- 寫檔慣例 `src/arcagi/hammer/formats.py`：`write_json` = `indent=1, sort_keys=True`＋換行；`write_jsonl` 排序 key 無縮排；`new_op()` 給全欄預設；自我檢查 `arcagi.hammer.check.check_root(root) -> list[str]`。
- **Argon 警告一現況已違反**：`epoch._main_run` gate_ids = L16∪P，P 的 gate_ok 進 `sleep_ops` 造候選（見 01a Q8）。
- GPU：gpusearch／GP 只評單支格子步驟程式，沒有評整棵樹的介面（D6）。

## 下一步

1. 讀 02b，把 Argon (A) 高嚴重項與 (B) 提案的採納與否記進代定清單（D11 起）；若改到塊 1，修正 D10。
2. 寫 `03-設計.md`：只細化**塊 1 往返工具**給 codex sol 施工。圖紙要點（隊長已定，見 D9、D10）：
   - 新套件 `src/arcagi/treegen/{__init__,boundary,export,import_,refs,diff,cli}.py`，入口 `python -m arcagi.treegen.cli roundtrip <tree_root> --out <dir>`。
   - 產物 `/home/lorkhan/code/playground-arc1/ws/evo/rt/hammer/{tree.json,state.json,files/,tree2/,tree2.json,diff.json}`（不進 git）；驗收 JSON `reports/think2-1109/rt/accept.json`（進 git）。
   - `tree.json` 格式照 02 塊 1（`schema:"aos-tree/1"`、`defs` 內容定址 sha12、`$ref` 只准 `#/defs/`、canonical dumps）。
   - 驗收：L1 `n_diff==0`；`--dedup off` 對照 `n_diff==0`；帶側車 import 時基因體檔位元組相同；tree2 `check_root` 錯誤數＝原樹；H8／H24 `ids_sha` 與 `frozen.holdout` 一致；單次 wall ≤5 s。L2 行為對照等塊 2。
   - 禁寫：活樹 `ws/hammer/` 任何檔、`src/arcagi/hammer/`、`native/`、`aos/`、`data/`、`wf/`、aos repo。
3. 施工：codex `-m gpt-6.1-sol -s workspace-write -C /home/lorkhan/repo/arcagi --add-dir /home/lorkhan/code/playground-arc1/ws/evo`（照 [思考輪-流程](../思考輪-流程.md) 實作指令，`/goal` 寫「實際跑一遍 roundtrip、accept.json pass=true」，任務書寫明不寫測試）；包 `systemd-run --user --scope --unit=arcagi-t2-build -p MemoryMax=12G nice -n 19`。隊長審 diff、實跑、commit。

## 在跑的背景單元

無（`arcagi-t2-gather`、`arcagi-t2-argon` 都已結束）。

## commit

- f160691 think-2: add gather (sol) and brief
- （本棒收尾 commit 見 git log）
