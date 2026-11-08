第二輪增補規劃：使用者 11-08 12:05 新想法「優化產生積木」到達時第一次規劃已施工完；fable 只讀 [01-簡報 §9 增補](01-簡報.md) 一次性產出，以下原樣存檔（隊長未改字）。

← [交棒總表](../README.md)｜[02 規劃](02-規劃-fable.md)｜[03 設計](03-設計.md)

# 第二輪增補規劃（fable）

## 本輪小施工單（1 條 opus 線，約 1 小時）

**範圍**：謂詞型積木的自動產生與記帳；其餘三型只定表示、不施工。
**檔案**：新增 `src/arcagi/dsl/predicates.py`（謂詞 AST 求值：`eq/ne/gt/lt/rank/and/or/not`，作用於既有 12 種物件屬性，≤300 行）；`objects_learner.py` 的選擇器改吃謂詞 AST（現有「單屬性等於」即深度 1 的特例，向後相容）；新增 `src/arcagi/blocks/gen_predicates.py`（產生器：枚舉單字面＋兩字面 AND／比較／排名，於 training 逐題評分，寫出 `aos/blocks/pred_<hash>/_metainfo.json`＋`_rule.json`，`_entry` 讀 stdin 物件 JSON 回 true/false）；`aos/pool` 加產生器節點 `aos/blocks/_gen/pred_combiner/`；測試 `tests/dsl/test_predicates.py`、`tests/blocks/test_gen_predicates.py`。
**介面**：`arcagi blocks gen-pred --split training --max-literals 2`；搜尋仍 in-process，registry 從資料夾載入 live 謂詞當選擇器。
**驗收**：training ≥79 不退、目標 ≥83；evaluation 不低於本輪第一次結果；每題 ≤3 秒、全量 ≤20 分鐘；產生的 live 謂詞 ≥20 個且 0 分者不落地；`ledger.jsonl` 出現產生器節點分紅；`aos-exec aos/blocks/pred_x` 對樣本物件回正確布林；commit 附改前／改後題數。
若剩時間才做 (b)：輸出尺寸公式枚舉（≤12 條式子）只當剪枝，不另開檔。

## 四型統一表示

共用外殼 `{"kind":..., "in":..., "out":..., "body":...}`，body 為 S-expression JSON；變數以字串引用屬性或抽取結果。

- 判斷型：`{"kind":"pred","in":"object","out":"bool","body":["and",["eq","color",3],["rank","size","max"]]}`
- 抽取型：`{"kind":"extract","in":"grid","out":"json","body":["count",["objects",["not",["touches_edge"]]]]}`
- 公式型：`{"kind":"formula","in":"features","out":"int","body":{"h_out":["*",2,"$n_obj"],"w_out":["*",2,"$n_obj"]}}`
- 變換型（現有，加參數引用）：`{"kind":"transform","body":[["select_objects","$pred:pred_a1"],["recolor","$extract:dominant"]]}`

接法：謂詞當選擇器參數；抽取結果以 `$extract:` 當變換參數來源；公式先定輸出尺寸，搜尋只保留尺寸相符的程式。

## 第 1～4 題推薦

1. 統一用「kind＋S-expression body」：一個求值器服務四型，LLM 可直接寫、資料夾可純資料落地、覆蓋與退休共用一套帳。
2. 最小版做 (a) 謂詞自動組合：物件層與選擇器已在，只補 AST 與枚舉器，且直接攻同大小 270 題的最大池；(b) 只在剩時間時當剪枝。
3. 只用 training 評分：分數＝能在該題所有 train pair 一致分開變／不變物件的題數，減字面數×0.5；0 分不落地、同判決較短者蓋住較長者標 `covered`；防背答案靠「全部 pair 一致＋≤2 字面」，evaluation 絕不參與評分；產生器本身是節點，收其子謂詞收入的 20%（沿 node-pool 80/20）。
4. 第三輪起走元優化：產生器參數（字面集、深度、評分式）本身成節點競爭。

## 第三輪起路線

r03：抽取型與公式型落地（計數、關係、尺寸公式），LLM 經 `aos-llm` 看未解題寫四型 JSON，執行器驗 train，量提案通過率；謂詞加 OR／關係字面（同色、相鄰、包含）。r04：產生器的產生——多個產生器各帶 `_metainfo` 成本與分紅，連續 0 分建議退休；想法 21 壓縮全面套到四型。遠期：由帳本驅動哪類積木值得再生，形成自我長大的種子。
