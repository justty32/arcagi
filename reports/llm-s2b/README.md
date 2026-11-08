# 支線 S2 第二任：把 LLM 解法蒸餾成積木、擴大 training 樣本

← [支線清單](../../notes/rounds/支線.md)｜第一任 [llm-s2](../llm-s2/README.md)｜交接 [llm-handoff](../llm-handoff.md)｜工具 [distill.py](../../src/arcagi/llm/distill.py)

## 結論

- **新樣本 s40**：r05 沒解的 training 隨機抽 40 題，**過 train 15/40，test exact 15/40**，沒有一題過 train 卻答錯。平均最佳 train 通過率 0.456；每題約 **20.6k token、53 秒**。逐題結果在 [s40.csv](s40.csv)。
  - 前 16 題用第一任的派法，過 5 題。後 24 題在派法裡加了「至少 check 4 次」，過 10 題。agent 不被要求的話，常常 check 一次就放棄。
- **大表改寫 gen1**：之前靠手抄大表過 train 的 10 題（`local_rule` 表 16～1656 列），要求改寫成短規則（表 ≤8 列）。**9/10 改寫成功，test 全對**（逐題在 [gen1.csv](gen1.csv)）。
  - a85d4709 主線還沒解，這裡有了短解。1190e5a7 的短解只用三步：`x_compress dup → pad → downscale`。
  - 這是這一任最直接的蒸餾：把背下來的答案換成一般規則。
- **候選與 live**：候選從 34 個增加到 73 個。照第一任的判法 rescore，**live 從 2 個增加到 12 個**。扣掉主線產生器判成 covered 的 4 個，剩 **8 個**：

| 候選 | 型 | 內容 | training 支撐（r04 沒解的） | 合成集 |
|---|---|---|---|---|
| `05ade5e13a` | transform | `x_connect hv` | 4（3） | 4/4 過半 |
| `5aa214b429` | transform | `x_period fill 0` | 5（5） | 只有 1/5 過半，寫死顏色 0，算背答案 |
| `087f839827` | transform | 第一任的兩步巨集 | 3（2） | 2/3 |
| `155b3ac577` | extract | 最近同色對齊物件的方向 | 6（5） | — |
| `390df7c974` | extract | 有洞物件的顏色 | 2（2） | — |
| `595cbf9534` | extract | 大小 >1 物件的顏色 | 2（2） | — |
| `4f7d8ff08a` | pred | `size > 1` | 13（9），主線判 live | — |
| `72c8aab4f1` | pred | 第一任的 rank shape_count | 12（9），主線判 live | — |

- 每一個都在**沒見過的 training 題**上有支撐，也就是支撐題不只是它的出處題。
- `x_*` 原語在 Python search 裡不會被提出（`PYTHON_SEARCH=False`），包成 macro 之後，Python search 才拿得到。
- 還沒做：真正的 search A/B（加進片段積木後 search 多解哪些題、退步幾題）。工具已經寫好，等主線全量跑完才能跑。跑法見 [交接](../llm-handoff.md)。

## 缺什麼原語（給 S1／S3／主線）

LLM 沒過的題，把它寫的 missing 一題一題分類，四任 run 合計：[missing.csv](missing.csv)。

| # | 缺的原語 | 題數 | 建議歸屬 |
|---|---|---|---|
| 1 | 線與射線的變體：兩點連線、對角線、每格都射、遇到換色才停 | 9 | S1 |
| 2 | 可以指定背景色或補邊顏色（物件抽取、`resize_crop`、`self_tile`） | 7 | S3（物件側）＋S1（補邊側） |
| 3 | 排序或排版：依數量或大小排顏色，把物件排成新版面 | 7 | S1 |
| 4 | 在標記處蓋模板（可翻轉、旋轉、縮放） | 6 | S1／S3 |
| 5 | 修補之後裁到原本洞的 bbox（`symmetrize`／`x_period` 之後接 crop） | 3 | S1 |
| 6 | 週期延續的變體：單一軸向、相位、奇偶 | 3 | S1 |
| 7 | 相對位置選擇器、每物件分象限、找最近物件 | 3 | S3 |
| 8 | 每物件填滿 bbox、外擴一圈、只在 bbox 內換色 | 3 | S3 |

蒸餾時另外看到的訊號（不是 missing，是改寫時一再出現的重複結構）：

- **旋轉封閉的局部規則**：6 題的短解寫成「同一張表 × `rot90` 四次」。如果 `x_vrule` 或 `local_rule` 有旋轉對稱的選項，這類解只要一步。→ S1
- **鄰居萬用字元**：8 列的表其實是把三個鄰居的「bg 或出界」逐一列出來。`local_rule` 如果有「任意」或「非前景」這種 token，表會縮成 1 列。→ S1
- **補一圈／去一圈**：b60334d2 要用 `resize_crop` 搭兩次 `rot180` 才補得出一圈邊，`pad`／`unpad` 應該做成原語。→ S1
- **`x_period fill` 的洞色**：它只吃寫死的顏色，合成集一換色就不過。改成可以吃 extract 給的顏色。→ S1
- 已經處理的：`n_holes`（主線 8a563db）、顏色變數 `local_rule`（S1 `x_vrule`，順帶解了 025d127b、1190e5a7）。

## 代定

1. s40 從 r05 沒解的 training 題裡抽，排除第一任 dev1／dev2 用過的題。seed 20261108。
2. 派法中途加了「至少 check 4 次」（從第 5 批開始），所以 s40 是兩種派法混在一起，報告裡分開列。`solver.md` 沒改。
3. `dsl.md` 加進主線和 S1 新做的原語，屬於詞彙同步，不是調提示；evaluation 沒用來調任何東西。
4. distill 不切含學習終端（`colormap`／`local_rule`／`x_vrule`）的片段。理由是 registry 不載入含這些的 macro。
5. 合成集門檻沿用主線 r06：每個用法的通過率要 >50%，而且至少 2/3 的用法要過。

<details><summary>指令</summary>

- `python -m arcagi.llm prompts --split training --ids $(cat reports/llm-s2b/s40-ids.txt)`
- 每批跑完：`python -m arcagi.llm record ID aos/llm/responses/s40/ID.json --split training --run s40 --model claude-opus-5-5 --tokens T --seconds X`
- `python -m arcagi.llm rescore`，再 `summary --split training --run s40 --csv reports/llm-s2b/s40.csv`
- A/B：`python -m arcagi.llm distill stage OUT`，接著在 `OUT/base` 和 `OUT/llm` 各跑一次 search eval，最後 `distill reuse OUT OUT/base.json OUT/llm.json --record`
</details>
