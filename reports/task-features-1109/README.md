# task-features-1109：800 題任務特徵表

目的：給 ARC-AGI training＋evaluation 共 800 題各一列「這題長怎樣、GPU 窮舉能逼多近」的特徵，供後續分群、選題、預測難度。

已抽到 [features.csv](features.csv)（800 列 × 62 欄，800 題全有 GPU profile）。過程與規格見 [progress.md](progress.md)、[gpuprofile-spec.md](gpuprofile-spec.md)。

## 重建

```sh
# 1) GPU 剖面（各約 0.5 GB 顯存，兩程序並跑約 2 小時）；產物 profile/*.jsonl 各約 2.5 MB，不入庫（.gitignore）
#    參數 --depth 5 --dedup 3 --budget 20；指令見 profile/training.txt、profile/evaluation.txt
# 2) 彙表（純 stdlib，數秒）
python3 native/tools/profile_features.py reports/task-features-1109/profile/training-d5.jsonl \
  reports/task-features-1109/profile/evaluation-d5.jsonl --out reports/task-features-1109/features.csv \
  --solved reports/native-cuda-1109/mainline-solved-*.txt
```

## 欄位說明

分數定義：程式在全部 train pair 上的輸出與目標比格，`denom` 累加 `max(輸出面積, 目標面積)`；`raw`＝相同格／denom；`score`＝套「最佳單一一致 colormap」後相符格／denom。exact 或 colormap 解必為 1.0。

CPU 特徵（只看 train）：

- `task`：任務 id。
- `split`：training／evaluation。
- `mainline_solved`：主線（native-cuda gated r07／r08 名單）是否已解，1／0。
- `n_train`、`n_test`：train／test pair 數。
- `in_h_mean`、`in_w_mean`、`out_h_mean`、`out_w_mean`：輸入／輸出平均高寬。
- `same_shape`：每對輸入輸出同尺寸，1／0。
- `out_shape_const`：所有輸出同尺寸，1／0。
- `size_ratio_y`、`size_ratio_x`：輸出／輸入高（寬）比，各對一致才填，否則空。
- `area_ratio_mean`：輸出面積／輸入面積平均。
- `colors_in`、`colors_out`：輸入／輸出用到的色數（含背景）。
- `colors_new`、`colors_dropped`：輸出才有／輸入才有的色數。
- `objects_in_mean`、`objects_out_mean`：非背景 4-連通物件平均數。
- `changed_cell_frac`：同尺寸對中被改的格比例平均（無同尺寸對則空）。
- `identity_score`：空程式（原樣輸出）套最佳 colormap 的 score，即「什麼都不做」的底線。

GPU profile 特徵（`native/bin/gpuprofile`，17 原語，深度 ≤5，每深度留 top-K=8 去等價程式）：

- `profiled`：有剖面，1／0（本表全 1）。
- `alphabet`：原語表大小。
- `dedup`：去等價參數。
- `max_depth`：要求的最大深度（5）。
- `depth_reached`：預算內完整搜完的最深深度。
- `seconds`：該題 GPU 秒數。
- `space_total`、`valid_total`：各深度程式總數／可執行（不報錯）數加總。
- `best`：所有深度最佳 score。
- `best_depth`：最佳 score 首次出現的深度。
- `perfect_depth`：首次出現 score=1.0 的深度，0＝沒有。
- `perfect_total`：score=1.0 的程式總數。
- `ge90_total`：score≥0.9 的程式總數。
- `top1_score`、`top1_raw`、`top1_program`：全深度 top 程式依（score↓, raw↓, 長度↑）排第一者；程式以 `>` 串原語。
- `n_top`：各深度 top-K 合計條數。
- `best_d1`…`best_d6`：各深度最佳 score（沒搜到該深度則空；本輪 d6 全空）。
- `prim_<原語>`（17 欄：flip_lr flip_ud transpose rot90 rot180 rot270 anti_transpose upscale tile downscale mirror_tile crop_bbox gravity fill_enclosed split_overlay self_tile colormap）：全深度 top-K 程式中含該原語的比例。

## 統計

| | training | evaluation | 合計 |
|---|---|---|---|
| best=1.0 | 53 | 17 | 70 |
| best≥0.9 | 173 | 143 | 316 |
| best<0.5 | 33 | 39 | 72 |
| best 中位數 | 0.880 | 0.845 | 0.867 |
| 主線已解 | 147 | 56 | 203 |
| 已解且 best=1.0 | 49 | 15 | 64 |
| 未解但 best=1.0 | 4 | 2 | 6 |
| 未解但 best≥0.9 | 90 | 118 | 208 |

- `best - identity_score` 中位數僅 0.007；383 題最佳程式不比「原樣輸出」好（差 ≤0.001）。
- 未解但 best=1.0 的 6 題（train 全對、主線沒解，待查 test 是否也對）：training 2013d3e2、25d8a9c8、a79310a0、aabf363d；evaluation 66e6c45b、be03b35f。
- 主線已解 203 題中 139 題 best<1.0：主線靠本剖面 17 原語以外的手段解。
- best=1.0 的 top-1 程式最常見：`split_overlay>colormap` 20 題、`mirror_tile` 7 題。
- 深度：531 題搜完 d4、230 題搜完 d5、39 題只到 d3；GPU 總計約 4.0 小時（兩程序並跑）。
- 抽查（11-10）：3c9b0459 top1=`rot180` score 1.0；00d62c1b top1=`fill_enclosed>colormap` score 1.0，皆符預期。

白話版：[features-白話.md](../../notes/rounds/gpu-night-1109/features-白話.md)。
