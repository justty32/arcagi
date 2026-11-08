# dsl-search-r01：網格 DSL＋逐層枚舉（深度 ≤3、觀察等價去重、終端換色表／鄰域規則）在 evaluation 能解 ≥8 題

- 指令（`systemd-run --user --scope -p MemoryMax=16G nice -n 19` 下跑）：
  `uv run arcagi eval --split evaluation --solver arcagi.solvers.search:solve --name dsl-search-r01 --timeout 10 --output artifacts/r01/dsl-evaluation.json --traces artifacts/r01/dsl-evaluation-traces.jsonl`（training 同，換 `--split training`）；
  比較 `uv run arcagi compare identity=reports/baseline-identity/identity-evaluation.json template=artifacts/r01/template-evaluation.json dsl=artifacts/r01/dsl-evaluation.json --format markdown`；commit `bee6426`。
- 結果：**evaluation 21/400（5.25%）**、training 57/400，errors=0，逾預算 0 題；全量耗時 evaluation 81 秒、training 60 秒（單題最長約 1 秒）。
- 基準：identity 0/400、0/400；template evaluation 0/400、training 6/400（template 的 6 題 dsl 全解，無退步）。
- 結論：**是**，超過 fable 驗收（evaluation ≥8、training ≥30）與目標（12、45）。

## 觀察

- evaluation 新解出 21 題：0c786b71、0c9aba6e、195ba7dc、31d5ba1a、34b99a2b、506d28a5、59341089、5d2a5c43、60c09cac、66f2d22f、68b67ca3、833dafe3、903d1b4a、9a4bb226、9ddd00f0、bf699163、cd3c21df、d19f7514、e133d23d、e345f17b、f823c43c。
- 解出的主力程式（evaluation）：`split_overlay+colormap` 10 題（切半做 AND/OR/XOR 再上色）、`symmetrize` 3、`crop_object` 3、鏡像鋪磚 3、縮放 2。
- training 按題型（inventory 標籤）解出：geometry 7/7、scale_tile 11/20、split_overlay 10/14、colormap 4/5、crop 6/30、fill 4/123、summary 4/26、move 3/18、same_mixed 3/63、shrink_other 3/32、symmetry 2/11；recolor／grow_other／remove 0。
- 過 train 但答錯（過擬合）：evaluation 10 題、training 22 題，多是「裁物件＋放大＋鄰域規則表」這類長程式在很小的輸出上背答案。試過「鄰域規則的每個變色鍵至少出現 2 次」：training 降到 54（少 3 題對、答錯降到 7），因 top-1 答錯不扣分而回退（代定 D7）。
- 搜尋遠沒用完預算（每題 2.5 秒、2 萬節點）：瓶頸是**原語覆蓋**，不是算力。

## 下一步

- 物件層（逐物件變換後畫回、依物件屬性上色）打 fill／recolor／same_mixed 大宗；格線切塊（cell grid）摘要。
- 用 `--traces` 的過 train 程式做第一次片段抽取（library learning 雛形）；過擬合題拿來試「多解投票／保留第二候選」。
