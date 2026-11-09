# think-2 進度（交接用）

← [代定清單](代定清單.md)｜[夜跑看板](../README.md)

狀態：**DONE（塊 1）**。第二棒（t2b）做完 D11～D20、03 設計、塊 1 施工（accept 三條全過）、04 總結。

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

## 第二棒做完

| 段 | 檔 |
|---|---|
| 代定 | [代定清單.md](代定清單.md) D11～D20 |
| 03 設計 | [03-設計.md](03-設計.md)（只塊 1） |
| 施工 | `src/arcagi/treegen/`（codex sol，隊長審 diff＋複跑），驗收 `reports/think2-1109/rt/accept.json` pass=true |
| 04 收輪 | [04-總結簡報.md](04-總結簡報.md) |

## 下一步

塊 2 的 03 細化（帶入 D11、D15～D17、D20），再交 sol 施工。

## 在跑的背景單元

無（`arcagi-t2-gather`、`arcagi-t2-argon` 都已結束）。

## commit

- f160691 think-2: add gather (sol) and brief
- （本棒收尾 commit 見 git log）
