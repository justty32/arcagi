第二輪規劃：fable 只讀 [01-簡報](01-簡報.md) 一次性產出，以下原樣存檔（隊長未改字）。

← [交棒總表](../README.md)｜下一步 [03-設計](03-設計.md)

# 第二輪規劃（fable）

**範圍**：主攻同大小題的物件層（S1）＋明顯分隔線格線切塊（S2）＋量具 top-2（S4）＋小規模 library learning（S3）；aos 接 A1～A4，本輪不碰 LLM。

**求解器方法**
- 新增原語（S1）：`objects` 抽取（4/8 連通、同色/多色、背景＝眾數），屬性：面積、顏色、bbox、正規化形狀、碰邊、有洞、同形計數、面積排名。動作以「選擇器＋動作」成對：`recolor_sel`、`delete_sel`、`keep_sel`、`move_sel`（往某方向到邊/碰撞）、`extend_sel`（畫線到邊）、`fill_holes`。選擇器限單一屬性述詞（＝值、最大、最小、唯一），由範例推：逐屬性檢查能否把 train 中「有變」與「沒變」物件完全分開，取最簡者；分不開即放棄該對。
- 新增學習器：`object_colormap`（屬性鍵→顏色表，終端不佔深度）；鍵在 train 至少出現 2 次、test 物件鍵必須全在表內，否則不產出，防背答案。
- S2：`split_grid` 只認整行整列單色分隔線（含外框）→小格陣列；`pick_cell`（唯一不同、最多色、含色 c）、`overlay_cells(and/or/xor)`、`cells_to_pixels`。等分無線格留第三輪。
- 搜尋：深度維持 3；物件層原語只在同大小或輸出為單物件 bbox 時進候選以控分支；每題時限 10 秒。
- 選解：最短程式優先；top-2＝與 top-1 輸出不同的次短程式，學習器類程式只能排第二。
- S3：從 r01 軌跡過 train 程式抽出現 ≥3 次的 2～3 步片段，登記為巨集資料夾（純 JSON）；解題集被更短程式涵蓋者標 covered（A4）。預期 +0～3，重點是骨架。

**aos 接入方案**（放 `aos/`）
```
aos/blocks/<name>/_metainfo.json   # kind、說明、參數域、cost、status
aos/blocks/<name>/_entry           # stdin 網格→stdout 網格；巨集另有 program.json
aos/solver/_entry                  # 包 arcagi 解一題
aos/pool/{config.json,wallets.json,ledger.jsonl,epochs/<n>.json}
```
- A1：registry 改成掃 `aos/blocks/` 讀 metainfo，按名字綁 Python 實作；搜尋仍 in-process，`_entry` 只是薄包裝（`python -m arcagi.dsl.run <name>`）。兩全之道：資料夾掌身分與帳，Python 掌速度。巨集＝只有 metainfo＋program.json 的資料夾，不改程式碼。
- A2：`aos/solver/_entry` 經 `aos-exec` 跑 20 題小集合，結果須與 in-process 一致。
- A3 記帳：一次全量跑＝一個 epoch（training、evaluation 各一，標明資料集，只有 evaluation 算正式）。每解一題收 1000；20% 留頂層，80% 依選中程式中積木靜態引用次數均分；花費＝積木被搜尋呼叫次數×metainfo cost（預設 1/千次）；房租每 epoch 100；連續 3 epoch 收入 0 只寫「建議退休」進 epochs 報告。r01 軌跡回放作 epoch 0。近失敗依引用積木追加 `_gradients.jsonl`（題號、程式、過幾例）。
- 不接：A5 額度緊且需 daemon；A6 aos 自身未定型。

**驗收數字**
- evaluation top-1 下限 30、目標 36，同大小切片 ≥10；top-2 另列不計主分。training 下限 75、目標 90；過 train 答錯 ≤15。
- 每題 ≤10 秒；全量 ≤12 worker、`nice -n 19`，training/evaluation 各跑一次。
- pytest：物件抽取與屬性、選擇器推斷、格線切塊、top-2 計分、registry 由資料夾載入、帳本守恆（收入＝分紅＋留存＋花費）。
- aos 可觀察驗收：(a) `echo 網格 | aos-exec aos/blocks/colormap` 回網格；(b) `arcagi eval --external "aos-exec aos/solver …"` 20 題與 in-process 同分；(c) `ledger.jsonl` 含 epoch 0、1，`wallets.json` 總和對帳；(d) 至少一個巨集資料夾由 S3 產生並標 live 或 covered。

**第 7 節推薦答案**
1. 順序 S4→A1→S1→S2→S3+A4→A3→A2；S1 是最大池子，S4 最便宜且應先定量具。
2. 選擇器＋動作原語對，選擇器限單屬性且須完全分開 train 物件；空間是屬性數×動作數，不爆炸也不背答案。
3. 只做明顯分隔線（含外框）；等分無線邊緣情況多，留第三輪。
4. 做，但只當骨架與 covered 演示；78 題原料不足以產生真增量。
5. 加 top-2，top-1 仍為主分；符合 ARC 兩次嘗試規則又不汙染主量尺。
6. 接 A1～A4，放 `aos/`；資料夾掌身分與帳、Python 掌速度。
7. 收入 1000/題、花費＝呼叫次數×cost、房租固定、epoch＝一次全量跑；ARC 無 token，呼叫次數最能反映誰在吃搜尋預算。
8. 不碰；額度 >85%，先把確定性部分做實。

**第三輪預告**：等分格與物件移動/碰撞類原語；用 r02 軌跡（預期 100+ 題）做真正的 library learning 與 covered 壓縮；以 aos-llm 小樣本 20 題量「提案→驗證」通過率（S5/A5）；帳本累到第 3 個 epoch，首次看退休建議。
