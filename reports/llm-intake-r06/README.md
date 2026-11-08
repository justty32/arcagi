第六輪線 C：S2 候選經影子門檻入庫。影子工具、預核、候選判定、子集前後。2026-11-08。

← [r06 設計](../../notes/rounds/r06/03-設計.md) §2–3 線 C｜[支線](../../notes/rounds/支線.md) S2／S5｜S5 合成集 [synth-s5](../synth-s5/README.md)

## 1. 影子工具

```sh
systemd-run --user --scope -q -p MemoryMax=8G nice -n 19 \
  uv run python -m arcagi.shadow <積木資料夾|_rule.json|裝積木的資料夾 …> \
  [--blocks-root aos/blocks] [--status live covered] [--kind pred extract formula macro] \
  [--reference reports/synth-s5/overfit.json] [--out x.json] [--quiet]
```

- 不寫 `aos/blocks/`；印表＋JSON 摘要，`--out` 存逐顆結果（support、各題合成小樣本過率、重複對象、原因）。
- 門檻（`src/arcagi/shadow/__init__.py` 常數）：
  1. training support ≥1 題（用各產生器自己的判定：formula `problems+holds`、pred `segments+mask`、extract `score_candidates`／`objrule.gen.score`；macro＝每個 train pair 都重現）；
  2. 支持題中 ≥2/3 題「合成多數過」＝`data_synth` 24 個合成 pair 切 8 份×3，≥4 份仍 support（pred 同為 2/3，隊長 r06 調整；原設計要求全過）；
  3. 不與 live 同種積木重複（同 body，或 training support 集合相同；macro 只比 body）；
  4. macro 額外要求每步都在 registry `ALL` 裡，否則 catalog 會靜默略過（`colormap`／`local_rule` 是終端學習器，不在 `ALL`）。
- 輸入格式與 A 線產出相同（積木資料夾），可直接重用。
- `--reference` 以 S5 `overfit.json` 逐積木標籤出混淆表（§2）。

## 2. 預核（開工時 HEAD `0c10a09` 的 aos/blocks 快照，產生積木 live＋covered 186 顆）

| 種類 | live 過／總 | covered 過／總 |
|---|---|---|
| extract | 14／50 | 4／14 |
| formula | 9／35 | 27／27 |
| pred | 11／60 | 0／0 |
| **合計** | **34／145** | **31／41** |

- 共 65／186 過；不過原因：合成多數 121、重複 2（無「無 support」：重算 support 與 metainfo 一致）。逐筆宣稱的多數不過率 20.9%（S5 報 18.7%，積木集不同）。
- 有帳收入三顆：`extract_f23ec080` 過；`formula_0832d6a3`（0/4）、`extract_713b1328`（2/4）不過——照設計不退休，只是影子門檻下不算好積木。
- 與 S5 標籤一致率（只比 support＋合成部分）：

| S5 標籤 | 影子好／S5 好 | 影子好／S5 壞 | 影子壞／S5 好 | 影子壞／S5 壞 | 一致率 |
|---|---|---|---|---|---|
| 多數（≥2/3 宣稱小樣本過 ≥50%） | 65 | 0 | 0 | 121 | 100% |
| 嚴格（≥2/3 宣稱 24 個合成 pair 全過） | 37 | 28 | 0 | 121 | 84.9% |

多數標籤是同一規則由 S5 腳本獨立算出，100% 表示實作一致；嚴格標籤下影子門檻較寬（28 顆嚴格判壞而影子放行），不會誤殺嚴格判好的。

原始：[precheck.json](precheck.json)。

## 3. S2 候選判定（`aos/llm/candidates/` 37 顆；34 顆已 commit＋3 顆 S2 施工中新增）

逐顆判定與原因已抽到 [verdicts.json](verdicts.json)（37 列；完整 support／小樣本過率在 [candidates.json](candidates.json)）。欄位：`candidate` 候選 hash、`llm_kind` 原型別、`block_kind` 入庫型別（transform→macro）、`support` training 支持題數、`synth_ok` 合成多數過題數、`verdict`、`reasons`。

- 過 11／37：macro 9／22、formula 1／6、pred 1／3、extract 0／6。
- 不過原因（一顆可多項）：合成多數不過 19、macro 含 registry 外步驟（`colormap`／`local_rule`）7、與 live 重複 6、training 無 support 2。
- S2 自判 live 的兩顆：`087f839827`（macro，support 3，合成 2/3 剛好過）**入庫**；`72c8aab4f1`（pred `["rank","shape_count","max"]`，support 12，合成僅 4/12）**不入庫**。

入庫（`aos/blocks/llm_<hash>/`，`source: llm`、`origin: <hash>`、`generator: _gen/llm`、metainfo 記 support 與 `shadow`）：

| 積木 | kind | support | 合成過 | 內容 |
|---|---|---|---|---|
| llm_087f839827 | macro | 3 | 2/3 | keep_sel 最多同形 → crop_object |
| llm_129466bfab | macro | 1 | 1/1 | crop_bbox → resize_crop h/2 w/2 |
| llm_28d1efd575 | macro | 1 | 1/1 | flip_lr → resize_crop 3×3 → flip_lr |
| llm_75210ea617 | macro | 2 | 2/2 | extend_from 最大物件方向（all） |
| llm_c2a3720e71 | macro | 2 | 2/2 | extend_from 最大物件方向（非最大） |
| llm_80875e5ba1 | macro | 1 | 1/1 | symmetrize both＋transpose |
| llm_999cf69827 | macro | 1 | 1/1 | symmetrize both |
| llm_e67436c9b5 | macro | 1 | 1/1 | symmetrize rot |
| llm_cb1618e21d | macro | 1 | 1/1 | resize_crop 2×2 |
| llm_277b40492f | formula | 1 | 1/1 | `["div","w",2]` |
| llm_89271108c6 | pred | 9 | 7/9 | `["rank","h","max"]` |

## 4. 子集前後（50 題 training，[subset.txt](subset.txt)：入庫積木支持的 19 題＋排序前 31 題）

| | 解出 | 過 train 答錯 | 耗時合計 |
|---|---|---|---|
| 入庫前（快照） | 15 | 11 | 72 s |
| 入庫後 | **18** | **8** | 120 s |

- 新解 3 題：`2013d3e2`（llm_129466bfab）、`5bd6f4ac`（llm_28d1efd575）、`d10ecb37`（llm_cb1618e21d），原本都是過 train 答錯；退步 0。這三題正是 S2 產生該候選的 training 題，屬「自題自解」，對 evaluation 的效益要看全量。
- 耗時 +68%（單 macro 不帶參數，但 9 顆加寬 BFS；最多 `09629e4f` 9.5→20.3 s）。照「不降不增才保留」→ 保留。
- 逐題：[subset-eval.json](subset-eval.json)。

指令（快照與入庫後各一份 blocks root，`ARCAGI_BLOCKS` 切換）：

```sh
S=<scratch>; git archive HEAD aos/blocks | tar -x -C $S   # 快照 → $S/blocks_snap
cp -r $S/blocks_snap $S/blocks_after
uv run python -m arcagi.blocks.gen_llm --root $S/blocks_after
for v in snap after; do ARCAGI_BLOCKS=$S/blocks_$v \
  systemd-run --user --scope -q -p MemoryMax=8G nice -n 19 uv run arcagi eval \
  --tasks-dir $S/subset --split training --solver arcagi.solvers.search:solve \
  --timeout 45 --workers 3 --output $S/eval-$v.json --traces $S/eval-$v-traces.jsonl; done
# 入庫：uv run python -m arcagi.blocks.gen_llm --out reports/llm-intake-r06/candidates.json
```

## 5. 留給隊長

- **帳不認 `llm_*`**：`blocks/pool/ledger.py` `_is_pred` 只認 `pred_`／`formula_`／`extract_` 前綴，`llm_89271108c6`（pred）、`llm_277b40492f`（formula）當參數用時不分紅；macro 以步驟名記帳不受影響。`dsl/features.source` 也只認 `extract_` 前綴（本輪沒有 llm extract 入庫，暫無影響）。
- **transform 含學習器步驟入不了庫**：7 顆含 `colormap`／`local_rule`（`program.run` 會跑，但 registry `ALL` 沒有，`registry` 載 macro 時略過）。要收得讓 registry 的 macro 執行改走 `program.run_step`。
- **單題 macro**：9 顆中 7 顆 support=1（設計門檻 ≥1）；若嫌加寬搜尋，可把 macro 的 support 下限改成 rescore 的 `MIN_MACRO_TASKS=3`（那樣只剩 `087f839827`）。全量耗時要留意。
- `gen_llm` 未接 `generator_budget`（延 r07）；只新增／刷新 `llm_*`，不退休。
- pytest：commit 前 419 passed（中途 S1 施工中的 `tests/native/test_ext_parity.py` 曾短暫失敗，非本線）。
