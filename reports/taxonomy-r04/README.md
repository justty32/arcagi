# taxonomy-r04：800 題兩層題型、r04 每類解題率、training 未解 50 題失敗原因

← [taxonomy](../../docs/taxonomy/README.md)｜類別表 [categories](../../docs/taxonomy/categories.md)｜[支線 S4](../../notes/rounds/支線.md)

- 指令：`python3 scripts/taxonomy_features.py`（特徵粗分）→ opus 子 agent 16 批×50 題照 [categories](../../docs/taxonomy/categories.md) 標（`scripts/taxonomy_show.py` 看題，不看 test 答案）→ `python3 scripts/taxonomy_merge.py`（合併、套 [overrides](../../docs/taxonomy/overrides.csv)、驗證 800 題全標）→ `python3 scripts/taxonomy_rates.py --run r04` → `python3 scripts/taxonomy_failsample.py --run r04`（seed 4）→ 3 個 opus 子 agent 寫失敗原因。
- 介面驗過：`uv run arcagi compare r03=… r04=… --labels docs/taxonomy/labels.csv --format markdown` 照主類分組正常；r05 報告出來後換 `--run r05` 重算即可。
- **evaluation 只用來報每類解題率**；逐題失敗機制只從 training 抽（主線 2026-11-08 指示）。

## 檔案

- [labels.csv](../../docs/taxonomy/labels.csv)：800 題 `task_id,category,subcategory`（交付物）；[labels-detail.csv](labels-detail.csv) 多 `confidence`（high 460／medium 298／low 42）與一句 `rule`。
- [rates.csv](rates.csv)：split（training／evaluation／all）× 層級（category／subcategory）× 類，欄位 `tasks,solved,rate,train_pass_wrong,near90,near_mean,half_fixed`。`half_fixed`＝未解題中最佳近失敗「修掉一半以上複製輸入會錯的格」（換尺寸題改用像素 ≥0.9），當「接近能解」的訊號。
- [failures.csv](failures.csv)：training 未解 50 題（依類別按比例抽），欄 `gap_type,missing_block,closeness,rule,why_fail`；抽樣與近失敗程式在 [failsample.json](failsample.json)。
- [features.csv](features.csv)、`batches/`、`labels/`：中間產物。

## 每類解題率（主類，r04）

| 主類 | 題數 | training | evaluation | 接近（all） | 過 train 答錯（all） |
|---|---|---|---|---|---|
| draw | 147 | 3/74 | 2/73 | 5 | 1 |
| recolor | 96 | 18/41 | 4/55 | 2 | 3 |
| pattern | 84 | 2/38 | 3/46 | **21** | 3 |
| objects | 81 | 2/42 | 1/39 | 11 | 0 |
| reshape | 62 | 1/26 | 1/36 | 2 | 5 |
| crop | 58 | 15/37 | 4/21 | 2 | **12** |
| move | 56 | 4/26 | 3/30 | **22** | 2 |
| scale_tile | 56 | 13/28 | 7/28 | 4 | 0 |
| fill | 53 | 5/29 | 1/24 | 1 | 0 |
| summary | 42 | 6/24 | 1/18 | 0 | **9** |
| overlay | 41 | 15/22 | 10/19 | 2 | 1 |
| multi | 15 | 0/5 | 0/10 | 1 | 1 |
| geometry | 9 | 8/8 | 0/1 | 0 | 0 |

- **題最多又最沒解**：draw 147 題只解 5（3.4%）、objects 81 解 3（3.7%）、reshape 62 解 2（3.2%）、pattern 84 解 5（6.0%）。
- **最接近能解**：move（22 題近失敗已修一半以上）、pattern（21）、objects（11）。
- **過 train 答錯集中**：crop 12、summary 9——選擇器／決勝規則過擬合，不缺積木。
- **recolor 落差最大**：training 44% → evaluation 7%，換色規則背了 training 的參數來源。
- 子類 0 解、題數多（all）：`draw.connect_points` 1/34、`draw.ring_around` 0/29、`objects.copy_stamp` 0/29、`pattern.continue_sequence` 0/29、`draw.path_bounce` 0/26、`reshape.assemble` 0/26、`recolor.by_position` 1/26、`draw.grid_lines` 1/22、`fill.bbox_or_gap` 0/21。

## training 未解 50 題：失敗原因

`gap_type`：缺原語 17、缺參數來源 15、缺週期／序列推斷 6、組合太深 5、過擬合／平手 3、輸出要從頭建 2、缺選擇器 2。closeness：near 32、medium 16、far 2。

跨題重複的缺塊（題號見 [failures.csv](failures.csv) 的 `missing_block`）：

1. **畫線族**（11 題）：兩點連線；射線帶色、雙向、撞障礙停、交叉換色；`extend_sel` 可用在第 2 步後。
2. **物件局部模板**（7 題）：`halo_sel`／`outline_sel`；`local_rule` 改用顏色角色（0ca9ddb6、7e0986d6 只差泛化）。
3. **計數／排名／層深當參數**（6 題）：依大小排名、環深度換色；`move_by(n=計數)`。
4. **以物件為對稱中心**（5 題）：`symmetrize(center=物件)`、跨最近物件鏡射。
5. **週期／序列外推**（5 題）。
6. **過擬合**（3 題；全體 crop 12＋summary 9 過 train 答錯）：程式對、決勝選錯。

## 主線下一步建議：前 5 個池子

| # | 池子 | 規模（all，r04 解） | 缺什麼 | 為什麼先做 |
|---|---|---|---|---|
| 1 | draw.connect_points＋ray_to_border＋grid_lines | 92 題（5） | 連線原語、射線帶色／停止條件／任意步可用 | 最大池、失敗樣本最常見（11/50） |
| 2 | pattern.*（對稱、週期修補） | 84 題（5），接近 21 | `symmetrize` 中心取自物件、週期外推 | 接近能解的題最多之一，近失敗已有骨架 |
| 3 | move.*（by_rule、toward_object） | 56 題（7），接近 22 | 位移量取自計數、每物件參數來源擴充 | 最接近能解（22 題已修一半以上） |
| 4 | draw.ring_around＋objects.outline_hollow | 42 題（1） | halo／outline 原語；`local_rule` 顏色角色化 | 幾乎全 0，但每題只缺一塊 |
| 5 | crop＋summary 決勝 | 21 題過 train 答錯 | 不缺積木：決勝與選擇器偏好 | 不加原語、純選擇規則，最便宜 |
