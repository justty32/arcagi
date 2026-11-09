# 整夜 GPU 暴力搜尋彙總（自動產生）

- 產生時間：2026-11-10T06:00:00+0800（由 `native/tools/gpu_overnight_summary.py` 寫）
- 原始輸出：`/home/lorkhan/repo/arcagi/reports/native-cuda-1109/overnight`（每題一行 JSON）
- 結束原因：到截止時間；截止 2026-11-10 06:00；日誌 `/home/lorkhan/repo/arcagi/reports/native-cuda-1109/overnight/run.log`

## 各階段

| 階段 | 題數 | 有 train 解 | 完整掃完 | 候選數 | GPU 秒 | 候選／秒 |
|---|---|---|---|---|---|---|
| phase-A | 800 | 73 | 795 | 4.87e+11 | 5604 | 8.68e+07 |
| phase-B | 178 | 1 | 155 | 1.52e+12 | 19883 | 7.67e+07 |

合計候選 2.01e+12，GPU 計時 25487 秒，平均 7.89e+07 候選／秒（GPU 與 LM Studio 共用）。

## 找到的程式

- 有 train 解的題：74；Python `arcagi.dsl.program` 重驗 train 全對 74/74，抽樣程式 143/143 train 全對。
- test 也對：66；其中主線（training gated-r07／evaluation gated-r08）未解的新題：**4**。
- 找到的解只寫在這裡，不進 `aos/blocks/`。

### 主線未解、test 對的題

| 題 | 集 | 深度 | 程式 |
|---|---|---|---|
| 46f33fce | training | 5 | `[["rot180"], ["downscale", 2, 2], ["rot180"], ["upscale", 2, 2], ["upscale", 2, 2]]` |
| 66e6c45b | evaluation | 4 | `[["gravity", "up"], ["gravity", "right"], ["mirror_tile", "quad"], ["downscale", 2, 2]]` |
| a79310a0 | training | 4 | `[["gravity", "down"], ["mirror_tile", "ud"], ["downscale", 2, 1], ["flip_ud"], ["colormap", [[8, 2]]]]` |
| be03b35f | evaluation | 3 | `[["split_overlay", "h", "left"], ["rot90"], ["split_overlay", "h", "nor"], ["colormap", [[10, 1]]]]` |

### 全部有 train 解的題

| 題 | 集 | 階段 | 深度 | train(Py) | test(Py) | 主線已解 | 程式 |
|---|---|---|---|---|---|---|---|
| 00d62c1b | training | phase-A | 1 | ✓ | ✓ | 是 | `[["fill_enclosed"], ["colormap", [[10, 4]]]]` |
| 0520fde7 | training | phase-A | 1 | ✓ | ✓ | 是 | `[["split_overlay", "v", "and"], ["colormap", [[10, 2]]]]` |
| 0c786b71 | evaluation | phase-A | 2 | ✓ | ✓ | 是 | `[["rot180"], ["mirror_tile", "quad"]]` |
| 0c9aba6e | evaluation | phase-A | 1 | ✓ | ✓ | 是 | `[["split_overlay", "h", "nor"], ["colormap", [[10, 8]]]]` |
| 0d3d703e | training | phase-A | 1 | ✓ | ✓ | 是 | `[["flip_ud"], ["colormap", [[1, 5], [2, 6], [3, 4], [4, 3], [5, 1], [6, 2], [8, 9], [9, 8]]]]` |
| 195ba7dc | evaluation | phase-A | 1 | ✓ | ✓ | 是 | `[["split_overlay", "v", "or"], ["colormap", [[10, 1]]]]` |
| 1b2d62fb | training | phase-A | 1 | ✓ | ✓ | 是 | `[["split_overlay", "v", "nor"], ["colormap", [[10, 8]]]]` |
| 1cf80156 | training | phase-A | 1 | ✓ | ✓ | 是 | `[["crop_bbox"]]` |
| 1e0a9b12 | training | phase-A | 1 | ✓ | ✓ | 是 | `[["gravity", "down"]]` |
| 1f85a75f | training | phase-A | 4 | ✓ | ✗ | 是 | `[["colormap", [[1, 0]]], ["colormap", [[2, 0]]], ["colormap", [[5, 0]]], ["crop_bbox"]]` |
| 2013d3e2 | training | phase-A | 4 | ✓ | ✗ | 否 | `[["crop_bbox"], ["mirror_tile", "quad"], ["downscale", 2, 2], ["downscale", 2, 2]]` |
| 239be575 | training | phase-B | 6 | ✓ | ✗ | 否 | `[["mirror_tile", "lr"], ["split_overlay", "v", "left"], ["split_overlay", "v", "and"], ["split_overlay", "v", "nor"], ["split_overlay", "h", "left"], ["split_overlay", "h", "or"], ["colormap", [[10, 8]]]]` |
| 25d8a9c8 | training | phase-A | 2 | ✓ | ✗ | 否 | `[["tile", 1, 3], ["downscale", 1, 3], ["colormap", [[1, 5], [2, 0], [3, 0], [4, 5], [6, 5], [7, 0], [9, 5]]]]` |
| 25ff71a9 | training | phase-A | 3 | ✓ | ✓ | 是 | `[["flip_ud"], ["mirror_tile", "ud"], ["downscale", 2, 1]]` |
| 27a28665 | training | phase-A | 5 | ✓ | ✗ | 否 | `[["mirror_tile", "quad"], ["fill_enclosed"], ["downscale", 2, 2], ["rot180"], ["downscale", 3, 3], ["colormap", [[0, 1], [1, 3], [5, 6], [8, 3], [10, 2]]]]` |
| 28bf18c6 | training | phase-A | 2 | ✓ | ✓ | 是 | `[["crop_bbox"], ["tile", 1, 2]]` |
| 31d5ba1a | evaluation | phase-A | 1 | ✓ | ✓ | 是 | `[["split_overlay", "h", "xor"], ["colormap", [[10, 6]]]]` |
| 3428a4f5 | training | phase-A | 1 | ✓ | ✓ | 是 | `[["split_overlay", "h", "xor"], ["colormap", [[10, 3]]]]` |
| 34b99a2b | evaluation | phase-A | 1 | ✓ | ✓ | 是 | `[["split_overlay", "v", "xor"], ["colormap", [[10, 2]]]]` |
| 3906de3d | training | phase-A | 1 | ✓ | ✓ | 是 | `[["gravity", "up"]]` |
| 3af2c5a8 | training | phase-A | 1 | ✓ | ✓ | 是 | `[["mirror_tile", "quad"]]` |
| 3c9b0459 | training | phase-A | 1 | ✓ | ✓ | 是 | `[["rot180"]]` |
| 44f52bb0 | training | phase-A | 2 | ✓ | ✗ | 是 | `[["gravity", "right"], ["downscale", 3, 3], ["colormap", [[0, 1], [2, 7]]]]` |
| 46f33fce | training | phase-A | 5 | ✓ | ✓ | 否 | `[["rot180"], ["downscale", 2, 2], ["rot180"], ["upscale", 2, 2], ["upscale", 2, 2]]` |
| 4c4377d9 | training | phase-A | 2 | ✓ | ✓ | 是 | `[["flip_ud"], ["mirror_tile", "ud"]]` |
| 506d28a5 | evaluation | phase-A | 1 | ✓ | ✓ | 是 | `[["split_overlay", "h", "or"], ["colormap", [[10, 3]]]]` |
| 5582e5ca | training | phase-A | 3 | ✓ | ✓ | 是 | `[["gravity", "down"], ["self_tile", "pos"], ["downscale", 3, 3]]` |
| 5614dbcf | training | phase-A | 1 | ✓ | ✓ | 是 | `[["downscale", 3, 3], ["colormap", [[5, 0]]]]` |
| 59341089 | evaluation | phase-A | 3 | ✓ | ✓ | 是 | `[["flip_lr"], ["mirror_tile", "lr"], ["mirror_tile", "lr"]]` |
| 5d2a5c43 | evaluation | phase-A | 1 | ✓ | ✓ | 是 | `[["split_overlay", "v", "or"], ["colormap", [[10, 8]]]]` |
| 60c09cac | evaluation | phase-A | 1 | ✓ | ✓ | 是 | `[["upscale", 2, 2]]` |
| 6150a2bd | training | phase-A | 1 | ✓ | ✓ | 是 | `[["rot180"]]` |
| 62c24649 | training | phase-A | 1 | ✓ | ✓ | 是 | `[["mirror_tile", "quad"]]` |
| 6430c8c4 | training | phase-A | 1 | ✓ | ✓ | 是 | `[["split_overlay", "h", "nor"], ["colormap", [[10, 3]]]]` |
| 66e6c45b | evaluation | phase-A | 4 | ✓ | ✓ | 否 | `[["gravity", "up"], ["gravity", "right"], ["mirror_tile", "quad"], ["downscale", 2, 2]]` |
| 66f2d22f | evaluation | phase-A | 1 | ✓ | ✓ | 是 | `[["split_overlay", "v", "nor"], ["colormap", [[10, 5]]]]` |
| 67a3c6ac | training | phase-A | 1 | ✓ | ✓ | 是 | `[["flip_lr"]]` |
| 67e8384a | training | phase-A | 1 | ✓ | ✓ | 是 | `[["mirror_tile", "quad"]]` |
| 68b16354 | training | phase-A | 1 | ✓ | ✓ | 是 | `[["flip_ud"]]` |
| 68b67ca3 | evaluation | phase-A | 1 | ✓ | ✓ | 是 | `[["downscale", 2, 2]]` |
| 6d0aefbc | training | phase-A | 1 | ✓ | ✓ | 是 | `[["mirror_tile", "lr"]]` |
| 6fa7a44f | training | phase-A | 1 | ✓ | ✓ | 是 | `[["mirror_tile", "ud"]]` |
| 72ca375d | training | phase-A | 5 | ✓ | ✗ | 是 | `[["colormap", [[2, 0]]], ["colormap", [[3, 0]]], ["colormap", [[7, 0]]], ["colormap", [[8, 0]]], ["crop_bbox"]]` |
| 7468f01a | training | phase-A | 2 | ✓ | ✓ | 是 | `[["flip_lr"], ["crop_bbox"]]` |
| 74dd1130 | training | phase-A | 1 | ✓ | ✓ | 是 | `[["transpose"]]` |
| 7b6016b9 | training | phase-A | 1 | ✓ | ✓ | 是 | `[["fill_enclosed"], ["colormap", [[0, 3], [10, 2]]]]` |
| 833dafe3 | evaluation | phase-A | 2 | ✓ | ✓ | 是 | `[["rot180"], ["mirror_tile", "quad"]]` |
| 8be77c9e | training | phase-A | 1 | ✓ | ✓ | 是 | `[["mirror_tile", "ud"]]` |
| 9172f3a0 | training | phase-A | 1 | ✓ | ✓ | 是 | `[["upscale", 3, 3]]` |
| 94f9d214 | training | phase-A | 1 | ✓ | ✓ | 是 | `[["split_overlay", "h", "nor"], ["colormap", [[10, 2]]]]` |
| 99b1bc43 | training | phase-A | 1 | ✓ | ✓ | 是 | `[["split_overlay", "h", "xor"], ["colormap", [[10, 3]]]]` |
| 9dfd6313 | training | phase-A | 1 | ✓ | ✓ | 是 | `[["transpose"]]` |
| a416b8f3 | training | phase-A | 1 | ✓ | ✓ | 是 | `[["tile", 1, 2]]` |
| a5313dff | training | phase-A | 1 | ✓ | ✓ | 是 | `[["fill_enclosed"], ["colormap", [[10, 1]]]]` |
| a740d043 | training | phase-A | 1 | ✓ | ✓ | 是 | `[["crop_bbox"], ["colormap", [[1, 0]]]]` |
| a79310a0 | training | phase-A | 4 | ✓ | ✓ | 否 | `[["gravity", "down"], ["mirror_tile", "ud"], ["downscale", 2, 1], ["flip_ud"], ["colormap", [[8, 2]]]]` |
| aabf363d | training | phase-A | 1 | ✓ | ✗ | 否 | `[["fill_enclosed"], ["colormap", [[2, 4], [3, 6], [4, 0], [6, 0]]]]` |
| b1948b0a | training | phase-A | 1 | ✓ | ✓ | 是 | `[["colormap", [[6, 2]]]]` |
| be03b35f | evaluation | phase-A | 3 | ✓ | ✓ | 否 | `[["split_overlay", "h", "left"], ["rot90"], ["split_overlay", "h", "nor"], ["colormap", [[10, 1]]]]` |
| c59eb873 | training | phase-A | 1 | ✓ | ✓ | 是 | `[["upscale", 2, 2]]` |
| c8f0f002 | training | phase-A | 1 | ✓ | ✓ | 是 | `[["colormap", [[7, 5]]]]` |
| c9e6f938 | training | phase-A | 1 | ✓ | ✓ | 是 | `[["mirror_tile", "lr"]]` |
| ce4f8723 | training | phase-A | 1 | ✓ | ✓ | 是 | `[["split_overlay", "h", "or"], ["colormap", [[10, 3]]]]` |
| d19f7514 | evaluation | phase-A | 1 | ✓ | ✓ | 是 | `[["split_overlay", "h", "or"], ["colormap", [[10, 4]]]]` |
| d511f180 | training | phase-A | 1 | ✓ | ✓ | 是 | `[["crop_bbox"], ["colormap", [[5, 8], [8, 5]]]]` |
| d5d6de2d | training | phase-A | 1 | ✓ | ✓ | 是 | `[["fill_enclosed"], ["colormap", [[2, 0], [10, 3]]]]` |
| dae9d2b5 | training | phase-A | 1 | ✓ | ✓ | 是 | `[["split_overlay", "v", "or"], ["colormap", [[10, 6]]]]` |
| e133d23d | evaluation | phase-A | 1 | ✓ | ✓ | 是 | `[["split_overlay", "v", "or"], ["colormap", [[10, 2]]]]` |
| e345f17b | evaluation | phase-A | 1 | ✓ | ✓ | 是 | `[["split_overlay", "v", "nor"], ["colormap", [[10, 4]]]]` |
| ed36ccf7 | training | phase-A | 1 | ✓ | ✓ | 是 | `[["rot270"]]` |
| f25fbde4 | training | phase-A | 2 | ✓ | ✓ | 是 | `[["upscale", 2, 2], ["crop_bbox"]]` |
| f25ffba3 | training | phase-A | 3 | ✓ | ✓ | 是 | `[["flip_ud"], ["crop_bbox"], ["mirror_tile", "ud"]]` |
| f2829549 | training | phase-A | 1 | ✓ | ✓ | 是 | `[["split_overlay", "v", "nor"], ["colormap", [[10, 3]]]]` |
| fafffa47 | training | phase-A | 1 | ✓ | ✓ | 是 | `[["split_overlay", "h", "nor"], ["colormap", [[10, 2]]]]` |
