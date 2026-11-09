# N4d：6 題「GPU profile train 全對、主線沒解」查 test

← 入口 [README](README.md)

## 結論

6 題中 **3 題 test 對**（a79310a0、66e6c45b、be03b35f），**3 題 test 錯**（2013d3e2、25d8a9c8、aabf363d，都是只在 train 上湊對的程式）。3 題對的題，主線用的原語都有（Python DSL 能直接跑這些程式），漏解的原因是**搜尋深度不夠**（2 題）和**守門／選擇**（1 題）。overnight native-cuda phase-A（`reports/native-cuda-1109/overnight/phase-A.jsonl`）早就搜到這 3 題且 `test_ok=true`，只是這些結果沒有接進主線。

## 1. test 對錯表

方法：從 `profile/*-d5.jsonl` 取各深度 top-K 中 score=1.0 的程式，依（score↓, raw↓, 長度↑）排序後取第一支當 top1。用 `arcagi.dsl.program`（CPU、Python 參考實作，在 task 背景 context 下）跑 train 與 test。profile 的 score 允許一個全 train 一致的 colormap，所以也在 train 上擬合同一個 colormap 再套到 test。腳本：[n4d/check_test.py](n4d/check_test.py)，輸出：[n4d/check_test.out.txt](n4d/check_test.out.txt)（含各題全部 score=1.0 的 top-K 程式）。

| 題 | split | top1 程式 | train | test |
|---|---|---|---|---|
| 2013d3e2 | training | `crop_bbox > mirror_tile quad > downscale 2,2 > downscale 2,2` | exact | **錯**（3×3 差 2 格） |
| 25d8a9c8 | training | `upscale 1,2 > upscale 1,2 > split_overlay v xor > split_overlay v nor > colormap` | exact | **錯**（差 3 格；其餘 18 支 score=1.0 也全錯） |
| a79310a0 | training | `gravity down > mirror_tile ud > downscale 2,1 > flip_ud > colormap 8→2` | exact | **對**（exact） |
| aabf363d | training | `colormap 4→0 > 2→4 > 6→0 > 3→6`（寫死顏色） | exact | **錯**（差 16 格；28 支全錯） |
| 66e6c45b | evaluation | `gravity up > gravity right > tile 3,3 > downscale 3,3` | exact | **對**（exact） |
| be03b35f | evaluation | `split_overlay h left > rot90 > split_overlay h nor > colormap` | exact | **對**（exact；第 2 支 `flip_lr>…>split_overlay v or` 錯 2 格） |

## 2. test 對的 3 題：主線為何沒解

資料：`artifacts/dsl-search-r06/`、`artifacts/gated-r07*/`、`artifacts/gated-r08/` 的 trace，`reports/gate-r07/*-tasks.csv`，`reports/gate-r08/README.md`。

- **a79310a0（搜尋深度）**：主線 C++ arcsearch 只搜到深度 2（28,609 節點、0.1 秒，沒有用完預算）。唯一過 train 的程式是記表型的 `self_tile>cells_to_pixels>x_vrule`，test 錯，被 r07 table 門擋下（all distrusted）後放棄。正解要 4 步加 colormap（其實就是「物件下移 1 格並改色」），主線搜不到這個深度，也沒有平移原語可以縮短。
- **66e6c45b（搜尋深度＋排序）**：主線 Python 搜尋出 9 支過 train 的程式，全是 `crop_bbox>…>local_rule` 記表型，test 都錯，r07／r07s1／r08 都判 all distrusted 而放棄。這些記表程式成本約 4.7，比較便宜，把候選位置佔滿；正解 `gravity×2>tile>downscale` 要 4 步組合，一直沒被生成（9 支裡沒有一支含 gravity）。
- **be03b35f（守門／選擇）**：主線其實解過這題。r06／r07／r07s1 都選 `keep_sel>overlay_cells>colormap` 並答對。r08 的 S1 native 支持度門（cf83c7f，連 colormap 也守，D-r7-18）把 26 支 C++ 解全擋掉，變成沒有候選。D-r8-21 已決定接受這 −1、不回改。

## 3. 給使用者裁的收編建議（未改主線、未改活樹）

1. **把 native-cuda gpusearch（phase-A 設定：`--depth 5 --dedup 3 --budget 120`）當成 gated 入口的另一個候選來源**，候選照樣過 guard。這 3 支正解都是純組合、不帶格表，table 門不會擋。a79310a0 是 **training** 題，能用 training 證明收益，不必拿 evaluation 調參（避開 D-r7-18／D-r8-21 的顧慮）。evaluation 的 66e6c45b、be03b35f 只當事後審計，不拿來當選門的依據。
2. 收編前要在 training 上量「過 train 答錯」會增加多少。這次 6 題裡有 3 題是 GPU 湊對：aabf363d 是寫死顏色的 colormap 鏈；25d8a9c8 有 19 支 score=1.0 全錯。建議 GPU 候選至少要過 r07 的 `table`／`unseen` 門，並要求同一個 test 輸出有 ≥2 支相異程式支持；be03b35f 的 top1 與第 2 支在 test 上答案不同，這點也要一起看。
3. 2013d3e2、25d8a9c8、aabf363d 不建議收。

## 安全

只寫本檔與 `n4d/`；只在 CPU 上跑（不到 1 分鐘），沒用 GPU，沒動主線、活樹或其他單元。
