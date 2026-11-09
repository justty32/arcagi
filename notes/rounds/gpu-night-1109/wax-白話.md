# 鑄蠟模（N1）白話進度

← [看板](README.md)｜比較 [compare.md](../../../reports/wax-night-1109/compare.md)｜交接 [progress](../../../reports/wax-night-1109/progress.md)

## 做了什麼

讓 LLM 寫「一步一步變網格」的小程式（蠟模），本機沙箱跑出每一步的中間網格，再把每一步丟給空樹搜尋（arcbatch，預算 200k）看能不能用幾個原語擬合出來。LLM 只產候選，最後仍由確定的程式驗證。

比了 4 種提示法（base＝r09 舊規矩、prims＝附 32 原語清單、prims_py＝原語寫成 Python 函式且每步一個運算式、prims_shot＝prims_py 加一個示範），模型用 litellm 的 sol-low／luna-low／terra-low；本地 gemma-e4b 因 LM Studio 被關、只有中途數據且全是 0。

## 數字（16 題 × 3 樣本）

- 最好：**sol-low · prims_py**——每次呼叫有 20.8% 機率拿到「每步都擬合得到、而且答案對」的蠟模；驗過的蠟模裡每步可擬合 51.4%。sol · base 主指標並列 20.8%，但步擬合只有 41.5%。
- luna 加原語清單後步變小（每步可擬合 23%→57～69%），但答案對的從 24 筆掉到 2～6 筆。
- terra 很慢（一次 50～100 秒），比較還在補跑，目前只有每法 8～9 筆。
- 16 題中只有 4 題拿到任何全步可擬合蠟模；r09 卡住的 b27ca6d3、2204b7a8 仍是零。

## 卡在哪

空樹的小程式最多 4 個節點，連「把 8 換成 2」這種換色都寫不出來，所以有換色的題一定有一步擬合不到——這不是提示能修的。

## 現在在跑

- `arcagi-n1-overnight`：sol-low · prims_py，296 題輪流鑄到 06:00，06:10 前寫 `reports/wax-night-1109/overnight-summary.md`。
- `arcagi-n1-cmp-terra`：terra 比較補跑。
- 本地 e4b 批次沒開：LM Studio 雖重開，但 e4b 未載入，送請求會觸發載入（違反不 load 規矩）。

## 下一步

先改語言（讓空樹能換色：放寬節點上限或加 `recolor` 原語），再回頭調提示；早上用整夜的蠟模算「哪些步反覆出現卻擬合不到」，當新原語候選。
