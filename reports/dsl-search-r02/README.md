# dsl-search-r02：物件層＋格線切塊＋自動產生的謂詞積木，在 evaluation 解 ≥30 題

- 指令（`systemd-run --user --scope -q -p MemoryMax=16G nice -n 19` 下跑）：
  `uv run arcagi eval --split evaluation --solver arcagi.solvers.search:solve --name dsl-search-r02 --timeout 15 --output artifacts/r02/dsl-evaluation-b.json --traces artifacts/r02/dsl-evaluation-b-traces.jsonl`（training 由 L4 線跑，輸出 `artifacts/r02/dsl-training-b.json`）；
  比較 `uv run arcagi compare r01=artifacts/r01/dsl-evaluation.json r02=artifacts/r02/dsl-evaluation-b.json --format markdown`；top-2 `uv run python scripts/score_top2.py <報告>`；記帳 `uv run python -m arcagi.blocks.pool --report <報告> --epoch N --split evaluation`。commit `75b90ed`。
- 結果：**evaluation 28/400（7.0%）**、training **79/400（19.75%）**，errors=0；每題最長 1.8 秒，全量 evaluation 約 140 秒。top-2 與 top-1 相同（28／79）。
- 基準：dsl-search-r01 evaluation 21/400、training 57/400；**退步 0 題**（兩個 split）。
- 結論：**否**（未達 fable 驗收 evaluation ≥30、同大小 ≥10）；training 達標（≥75）。方向對但 evaluation 增量小：新原語多在 training 的 recolor 類生效。

## 中間點

| 版本 | evaluation | training | 內容 |
|---|---|---|---|
| r01 | 21 | 57 | 整張網格 DSL |
| r02a（commit 4914c7a） | 27 | 79 | ＋物件選擇器／動作、object_colormap、格線 4 原語、5 個巨集、local_rule 排後、預算 5 秒 |
| r02（75b90ed） | 28 | 79 | ＋L4 自動產生謂詞（60 live）當選擇器 |

## 觀察

- evaluation 新解 7 題：12eac192、84f2aca1、ae58858e、bbb1b8b6、c3202e5a、d282b262、e0fb7511。**ae58858e 是自動產生的謂詞 `pred_06f2dc53`（`size > 3`）解的**：`[["recolor_sel","4same","pred","pred_06f2dc53",6]]`。
- 切片：evaluation 同大小 3→7/270（驗收 ≥10 未達）、格線盤面 7→9/77；training 同大小 23→37/262、格線 12→21/77。
- training 按題型：recolor 0→9/29、split_overlay 10→12、crop 6→8、fill 4→6、remove 0→2、summary 4→6、shrink_other 3→5、same_mixed 3→4；grow_other／move／symmetry 沒動。
- 過 train 但答錯：evaluation 12、training 20（r01 為 10、22），背答案問題沒解決。
- top-2 沒加分：搜尋停在第一個有解的深度，同深度的不同輸出很少（evaluation 只 3 題有第二候選）。
- 物件原語讓搜尋樹變寬 2.5 倍（L1 量），所以只允許當第一步（代定 D-r2-2）。
- L4 抽查：物件抽取用「整格眾數色」當背景，同一題不同 pair 的背景會不一致，謂詞選擇器因此轉不成解——下一輪先修。

## aos 帳（aos/pool/）

- epoch 0＝r01 evaluation 回放（收入 21000）、epoch 1＝r02a（27000）、epoch 2＝r02（28000）；三個 epoch 守恆檢查都成立。
- epoch 2 收入最高：colormap、split_overlay；產生器節點 `_gen/pred_combiner` 首次分到 80（來自 pred_06f2dc53 的 20%）。
- **第一次「建議退休」**（連續 3 epoch 0 收入）：anti_transpose、crop_bbox、flip_ud、gravity、local_rule、rot270、rot90、self_tile、transpose——只是建議，未退；其中幾何原語是巨集與組合的基礎，下一輪要設 `essential` 名單（node-pool 設計有這欄）。

## 下一步

- 物件背景偵測改成同題一致；抽取型／公式型積木（輸出尺寸公式、計數）；搜尋改成「同深度收集多解」才有實質 top-2；LLM 小樣本提案（aos-llm）。
