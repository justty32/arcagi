# think-2 進度（交接用）

← [代定清單](代定清單.md)｜[夜跑看板](../README.md)

狀態：**塊 1～4 完成**（塊 4 由 t2f 收：審 diff、實跑 1 代 8 個體，[b4/accept.json](../../../../reports/think2-1109/b4/accept.json) G1～G7 全 PASS）。塊 5 留下一輪。

**下一棒**：收輪 04b——寫塊 1～4 總結簡報（參考 [04-總結簡報.md](04-總結簡報.md) 格式），塊 5（Janet）留下一輪。

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

## 第四棒（t2d）做完

| 段 | 結果 |
|---|---|
| 塊 2 收 | [b2/accept.json](../../../../reports/think2-1109/b2/accept.json)：B1～B5 PASS（C25 wall≈15 s、C50 L=50k/6 ep≈33～38 s，check_root 0 錯；C25／C50 皆決定論 σ=0 degenerate；L2 Δ=0、cost 同）。B6：原 D20 三變體都因 variants 缺 `files/` 崩（mkvariants bug），補檔重跑 → v1、v3 Δ=0；**v2 改 born/by 快撥崩** → D20 不用，只用 `genome_sha`（已記代定清單） |
| 03c | [03c-設計-塊3.md](03c-設計-塊3.md)：回應 Argon 7（legacy／aos 兩組 rates，legacy 要 Δ=0）、8（兩層守恆、單輪新解題由 solutions 比對、10% 底薪保覆蓋）；開放 cost key 規則（點分、≥0、祖孫不並存、前綴 keys、rollup） |
| 施工 | codex sol：`treegen/{cost,credit,health,ledger}.py`、cli `ledger`／`ledger-check`、`tests/treegen/test_block3.py`（treegen 共 53 passed）、`reports/think2-1109/cost/rates_{legacy,aos}.json`、[b3/accept.json](../../../../reports/think2-1109/b3/accept.json) C1～C7 全 PASS、[b3/fake.json](../../../../reports/think2-1109/b3/fake.json) 8 種造假全 exit 1 |
| 實數 | legacy price Σ=218157376＝meter cost（Δ=0）；Σ amount=0.18335 vs meter eff 0.1834；守恆最大殘差 2.7e-20；live op 覆蓋 84/84；只 epoch 5 有新解題（1 題歸 comb_g1_cd450dff4b、1 題無 blk）；health：solve ok=false（dormant-stale 5 → retire_suggest 5 列），其餘 ok |
| 隊長審 | `ledger-check` 從活樹重算參考值再比對檔案（不信存檔 pass）；我另做「守恆但分錯」造假（epoch 2 第一層 gate+0.005、judge−0.005）→ C2 FAIL exit 1 |

產物（不進 git）：`ws/evo/ledger/hammer/`；造假：scratchpad `t2d/fake/`、`t2d/myfake/`。

已知限制：by_subtree 七節點等分（weight 全 1.0），第一層沒有區分力；gate／route 無 blk 歸屬，star 份額平分；花費只有 hammer 級；20/70/10 未證有效。

## 第五棒（t2f）做完：塊 4 收

| 段 | 結果 |
|---|---|
| 審 diff | sol 交付 `treegen/{bounds,check,crossover,fitness,ga,ga_fake,genome,mutate,select}.py`＋cli `ga`／`ga-check`／`ga-fake`、`tests/treegen/test_block4.py`。逐行看 check（op 的 id/kind/born/by/sig/parent_route 不可動、gate 只許數值參數、route 只許 priority、骨架除 judge 數值與 node weight 外不可動、懸空 $ref 先擋、genome_sha 重算比對、check_root＋leak）、genome.write 每次重算 sha、pack 由 deduplicate 重建 defs、select 只 copytree 到 hall/ 不刪、destination 限 ws/evo 或 scratch。唯一修改：`genome.SCRATCH` 由 t2e 改 t2f（暫存只落本棒 scratch） |
| pytest | `tests/treegen` 95 passed |
| 實跑 | `ga --pop 8 --gens 1 --seed 0`，總 ~25 s 快撥 wall 71 s（5 次實跑＋3 次快取命中）；G1～G7 全 PASS（重抽皆 0；G4 8/8 封印同 sha；G6 繼承 taint 96 列只診斷；G7 活樹 97 檔不變、95 passed） |
| 子代 | 0 M5 grow.weight 1→0.855（eff 2.7417）；1 M2 comb_g1_cd450dff4b live→dormant（eff 2.7245，cost↑）；2 M2 comb_g1_e6ba9d8a6f dormant→live（2.7406）；3 M3 刪 route_starve_rt_sleep（2.7417）；4 M2 同 route→dormant（2.7417）；5 X1(4,1)＝4 同 sha（快取）；6 X3(2,3)＝2 同 sha（快取）；7 clone（快取）。auc_L 全 20，Δ=0、σ=0 degenerate |

發現（未修，記給下一輪）：(a) 交配兩支都塌成親代之一的 genome（X1/X3 沒拒絕重複 sha，mutate 有）；(b) auc_L 對所有單刀突變都不動，C25 快撥的鑑別力不足，選擇只靠 eff 小數與 sha 字典序破平手——G 驗收證管線，不證演化有效；(c) 第一層分法仍 weight 等分。族群在 `ws/evo/pop/`（不進 git）。

## 下一步

1. **塊 4 整棵樹當遺傳個體**：先寫 03d（回應 D15 的 Argon 9 快撥覆寫 budgets 廢 M1、10 單親退化；採 02b (B)3 health 引導突變：讀 `health.json`／`credit.jsonl` 挑下刀 op）。個體 hash 只用 `genome_sha`（D20 不用）；顯著性用 `compare` 成對 σ（同樹 σ=0 degenerate）。
2. 突變要避開 born/by 欄位（v2 證實改 born 會讓快撥崩，先查 quick 哪裡讀 born.epoch）。
3. 第一層分法改「節點當輪活躍度」而非 weight，否則 by_subtree 無區分力（塊 4 適應度前要定）。

## 在跑的背景單元

- `arcagi-t2e-sol`（codex sol 施工塊 4）：任務書／log／回報在 scratchpad `t2e/{task.md,sol.log,sol-report.md}`；`systemctl --user is-active arcagi-t2e-sol.scope` 非 active＝跑完。跑完：審 diff → `systemd-run ... arcagi-t2e-ga` 跑 `python -m arcagi.treegen.cli ga --parent ws/evo/rt/hammer/tree.json --pop 8 --gens 1 --out ws/evo/pop --seed 0 --ledger ws/evo/ledger/hammer` → 看 `reports/think2-1109/b4/accept.json`。
