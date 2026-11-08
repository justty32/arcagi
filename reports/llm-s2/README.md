# 支線 S2 報告：LLM 提規則、程式驗（蒸餾第一步）

← [支線清單](../../notes/rounds/支線.md)｜程式 [src/arcagi/llm/](../../src/arcagi/llm/__init__.py)｜提示 [solver.md](../../aos/llm/prompts/solver.md)、[dsl.md](../../aos/llm/prompts/dsl.md)｜交接 [llm-handoff](../llm-handoff.md)

## 結論

- **evaluation 20 題（主線指定、r04 全沒解）：test exact 7/20**（同尺寸 4/10、尺寸會變 3/10）。過 train 的 7 題 test 全對，**過 train 答錯 0**。
- training 開發：dev2（r04「過 train 但 test 錯」的 24 題）test exact 12/24；dev1（隨機未解 7 題）2/7。
- 成本：evaluation 每題約 **21k token、51 秒**（opus subagent，4 題一批，token 按批平均分；取自 subagent 用量回報）。
- 候選積木 34 個，在 `aos/llm/candidates/<hash>/_rule.json`（含 `source:"llm"`、`model`、`prompt_hash`、`support_tasks`）。training 重評分後的 live：
  - `087f839827`（transform 巨集：`keep_sel 8same pred [rank shape_count max]` → `crop_object 8multi top_left`）：training 支撐 3 題（`library` 門檻 3），其中 2 題 r04 沒解；但 d9fac9be 用它 test 會錯，淨增 1 題（39a8645d）。
  - `72c8aab4f1`（pred `["rank","shape_count","max"]`）：在記憶體裡重跑 `gen_predicates` 的 judge（同預算 6390、同 live cap），排第 45 名，**live**。但這條字面量產生器自己也會列舉到（`enumerated: true`），所以不算 LLM 獨有的貢獻。
  - 其餘候選：已存在（和 `aos/blocks/` 現有積木同 body）、被蓋住或 0 分。
- **蒸餾訊號**：31 題沒過的，LLM 都寫了缺什麼原語（[missing.csv](missing.csv)）。重複出現的：物件原語要能指定背景色（4 題）、物件屬性 `n_holes`（3 題）、顏色當變數的 `local_rule`（有 4 題過 train，是靠手抄一張 n4／n8 大表硬湊的）。

<details><summary>數字明細與指令</summary>

| run | split | 題數 | 過 train | test exact | 平均最佳 train 通過率 | token／題 | 秒／題 |
|---|---|---|---|---|---|---|---|
| dev1 | training | 7 | 2 | 2 | 0.333 | 60.8k（單題一個 agent） | 48.9 |
| dev2 | training | 24 | 13 | 12 | 0.642 | 16.1k（4 題一批） | 27.1 |
| eval20 | evaluation | 20 | 7 | 7 | 0.404 | 21.2k（4 題一批） | 50.7 |

- 逐題：[dev1.csv](dev1.csv)、[dev2.csv](dev2.csv)、[eval20.csv](eval20.csv)。軌跡：`aos/llm/traces/<run>-<split>.jsonl`（`arcagi-llm-trace/1`，每條規則一行，含 idea／missing）。LLM 原始回答：`aos/llm/responses/<run>/`。
- eval20 解出：551d5bf1 639f5a19 94414823 ca8f78db（同尺寸）、695367ec e633a9e5 e7a25a18（尺寸會變）。
- 流程（每題）：`python -m arcagi.llm prompts --split S --ids ID` → subagent 只讀 `aos/llm/prompts/tasks/ID.md`＋`dsl.md`，用 `check`（只回 train 結果，最多 8 次）迭代，把答案寫進 `responses/` → 隊長跑 `record`（train＋test 評分、寫軌跡；只有 training 會落候選）→ `rescore`。
- 防背答案：提示只給 train pair 和 test input。evaluation 題只量分；提示只在 dev1 階段改過兩次（背景色段落、步驟 5「至少試兩種拆法」），兩次都在 eval20 開跑之前。evaluation 題不落候選。
- 驗證的背景色和搜尋一致（`task_background`，train 的 input＋output）。
- ledger 列建議（主線核後寫入）：`llm-s2-eval20 | evaluation 20 題子集 | 7/20 | opus subagent 提四型 JSON、程式驗 | commit 見 git log reports/llm-s2`。
</details>

## 代定

1. LLM＝Claude opus subagent（不用外部 API、不碰 LM Studio）。4 題一批，token 按批平均分。
2. 回答格式一律寫 transform，子規則（extract／pred／formula）內嵌成參數；落候選時再把子規則拆出來各自成為候選。
3. transform 至少要 3 題 training 支撐才算可重用巨集（同 `library.find_macros`）；不到 3 題的記 `solution_only`。
4. pred／formula 的 live 判定，是在記憶體裡重跑主線產生器的 judge；有標 `enumerated` 的，代表產生器自己也會列舉到。
5. dev 的選題偏「過 train 但 test 錯」和「近失敗」：這兩類最可能只差參數，最適合 LLM 補。
