# think-2 進度（交接用）

← [代定清單](代定清單.md)｜[夜跑看板](../README.md)

狀態：**塊 2 PARTIAL（t2c）**：03b 寫好、sol 施工完、隊長審過＋造假測試全過；§9 長跑在背景。塊 1 DONE。第二棒（t2b）做完 D11～D20、03 設計、塊 1 施工（accept 三條全過）、04 總結。

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

## 第三棒（t2c）做完

| 段 | 結果 |
|---|---|
| 03b | [03b-設計-塊2.md](03b-設計-塊2.md)：快撥（副本清 P＝D17、外框預算鎖死回應 Argon 9）、雜訊尺（成對 bootstrap＝D16）、守門一（config＋ops，分 inherited／new）、守門二（行級 sha 登錄，堵 Argon 6.1）、驗收 B1～B6 |
| 施工 | sol：`treegen/quick.py`、`noise.py`、`guards.py`、cli 加 5 子指令、`tests/treegen/test_block2.py`（14 passed）、`reports/think2-1109/guards/thresholds.json`（25 列，rank／diag／route，無收升退）；隊長審過登錄表與 quick 的 dest 限制、threads≤4、P 清空 |
| 守門實數 | 守門二 repo PASS（25 命中、未登錄 0）；造假 `if pixel_acc>0.9: promote` → FAIL（未登錄 2）。守門一 活樹 FAIL（config FAIL、16 violations／12 tainted ops）；快撥副本 config PASS、leak_new PASS（繼承 12 列 tainted，總 status FAIL＝預期）；造假加一列 src_tasks∋P → leak_new FAIL |
| 雜訊尺造假 | 同份 quick 兩次 → deterministic、σ=0（degenerate）；翻一題 → deterministic=false、exit 1、mismatch 1；compare Δ=1、σ=1.02、z=0.98 |
| 煙霧 | L=2000/1 epoch：auc_L 3＝Σper_task，check_root 0 錯 |

造假產物：scratchpad `t2c/fake/`。

已出的 §9 數字：C25（L=25k、epochs 0..4）淨態 ×3：wall 15.5／15.2／14.2 s（load≈8～10），auc_L 20、cost 7294813、eff 2.7417 三次全同 → deterministic，`sigma_auc_L`=0（degenerate）；guards leak_config／leak_new 皆 PASS。C50、B5、B6 待收。

## 下一步

1. 收 §9 長跑結果（下節單元）：讀 `ws/evo/quick/b2runs.out`、`noise-c25.json`、`noise-c50.json`、`cmp-l2.json`（B5 要 Δ=0）、`cmp-d20-v{1,2,3}.json`（B6）、`cmp-clean-vs-state.json`、各 `quick.json` 的 wall／guards，寫 `reports/think2-1109/b2/accept.json`（B1～B6）並 commit，代定清單 D20 依 B6 結果改「驗過可用／不用」。
2. 若 C25/C50 全決定論，`sigma_auc_L` 對同樹會是 0（degenerate），塊 4 判顯著要用 `compare` 的成對 σ（不同樹）。
3. 之後：塊 3 credit 帳的 03 細化（先回應 D15 的 Argon 7、8）。

## 在跑的背景單元

- `arcagi-t2c-b2runs.service`（systemd 服務，非 scope）：腳本 scratchpad `t2c/b2runs.sh`，C25×3→noise→L2 兩跑→D20 三變體→C50×3→noise；輸出 `/home/lorkhan/code/playground-arc1/ws/evo/quick/`，跑完印 `ALLDONE`。C25 一跑約 15 s。

## commit

- f160691 think-2: add gather (sol) and brief
- （本棒收尾 commit 見 git log）
