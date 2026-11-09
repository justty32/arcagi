# GP 整夜彙總（gpgp，11-09→11-10）

產生時間 2026-11-10T06:00:00。結束原因：到截止時間；截止 2026-11-10 06:00；日誌 `/home/lorkhan/repo/arcagi/reports/gpu-gp-1109/overnight/run.log`

- 題池：主線未解的 training＋evaluation 題；跑過 597 題，GPU 累計 6.89 小時。
- GP 解出（train 全對）：**11** 題；Python 重驗 train 對 11、test 對 **2**。
- 化簡後深度分佈：{0: 1, 2: 1, 4: 4, 7: 2, 8: 3}

| 輪 | 題數 | 解出 | GPU 秒 |
|---|---|---|---|
| pass-1 | 597 | 11 | 11837 |
| pass-2 | 216 | 0 | 12978 |

## 解出清單

| 題 | 輪 | 深度 | 種類 | 秒 | Python train | Python test | N2 窮舉也解出（深度） | 程式 |
|---|---|---|---|---|---|---|---|---|
| 1fad071e | pass-1 | 7 | colormap | 10.9 | True | False | 否 | `[["downscale",3,1],["downscale",3,1],["tile",1,2],["colormap",[[2,0]]],["crop_bbox"],["gravity","right"],["split_overlay","v","or"],["colormap",[[10,1]]]]` |
| 2013d3e2 | pass-1 | 4 | exact | 0.4 | True | False | 是（4） | `[["crop_bbox"],["mirror_tile","quad"],["downscale",2,2],["downscale",2,2]]` |
| 239be575 | pass-1 | 8 | colormap | 5.2 | True | False | 是（6） | `[["mirror_tile","ud"],["split_overlay","h","xor"],["split_overlay","h","xor"],["split_overlay","h","or"],["transpose"],["gravity","up"],["split_overlay","h","left"],["split_overlay","h","xor"],["colormap",[[0,8],[10,0]]]]` |
| 25d8a9c8 | pass-1 | 2 | colormap | 0.1 | True | False | 是（2） | `[["downscale",1,3],["tile",1,3],["colormap",[[1,5],[2,0],[3,0],[4,5],[6,5],[7,0],[9,5]]]]` |
| 66e6c45b | pass-1 | 4 | exact | 0.2 | True | True | 是（4） | `[["gravity","right"],["gravity","up"],["mirror_tile","quad"],["downscale",2,2]]` |
| 8597cfd7 | pass-1 | 8 | colormap | 3.9 | True | False | 否 | `[["mirror_tile","quad"],["split_overlay","h","or"],["split_overlay","h","xor"],["transpose"],["split_overlay","h","or"],["split_overlay","h","xor"],["split_overlay","v","xor"],["split_overlay","h","or"],["colormap",[[0,2],[10,4]]]]` |
| a79310a0 | pass-1 | 4 | colormap | 1.6 | True | True | 是（4） | `[["gravity","down"],["mirror_tile","ud"],["downscale",2,1],["flip_ud"],["colormap",[[8,2]]]]` |
| aabf363d | pass-1 | 0 | colormap | 0.1 | True | False | 是（1） | `[["colormap",[[2,4],[3,6],[4,0],[6,0]]]]` |
| be03b35f | pass-1 | 4 | colormap | 0.2 | True | False | 是（3） | `[["split_overlay","h","and"],["flip_lr"],["gravity","down"],["split_overlay","v","nor"],["colormap",[[0,1],[10,0]]]]` |
| d9fac9be | pass-1 | 7 | colormap | 6.0 | True | False | 否 | `[["downscale",1,3],["gravity","up"],["crop_bbox"],["gravity","left"],["crop_bbox"],["downscale",1,3],["crop_bbox"],["colormap",[[3,8]]]]` |
| f8ff0b80 | pass-1 | 8 | colormap | 15.5 | True | False | 否 | `[["downscale",2,2],["colormap",[[0,8]]],["gravity","left"],["rot180"],["downscale",2,2],["colormap",[[4,0]]],["downscale",1,3],["gravity","down"],["colormap",[[0,4],[2,3],[3,8],[8,2]]]]` |

GP 解出而 N2 窮舉（截至彙總時）未解出：4 題：1fad071e, 8597cfd7, d9fac9be, f8ff0b80。

找到的解只寫報告，不進 `aos/blocks/`。原始資料：`/home/lorkhan/repo/arcagi/reports/gpu-gp-1109/overnight/pass-*.jsonl`。
