# S2 交接（aos-llm 蒸餾第一步）

← [S2 報告](llm-s2/README.md)

## 現況（2026-11-08）

- 驗收：20 題 evaluation 已跑完，test exact 7/20；有 ≥1 個候選在 training 重評分後是 live（`087f839827` 巨集、`72c8aab4f1` pred，細節見報告）。主線第六輪的線 C 會唯讀 `aos/llm/candidates/*/_rule.json` 影子跑一遍，收編進 `aos/blocks/llm_*`，沒收的理由寫在 `reports/llm-intake-r06/`。
- 程式：`src/arcagi/llm/`，子模組 tasks／verify／candidates／rescore／mainline／trace／`__main__`；測試在 `tests/llm/`（10 個，綠）。

## 怎麼接著跑

1. 先寫提示：`nice -n 19 uv run python -m arcagi.llm prompts --split training --ids …`
2. 開 opus subagent（同時 ≤3 個），提示照抄：「Follow the instructions in /home/lorkhan/repo/arcagi/aos/llm/prompts/solver.md exactly, once per task…: TASKS=… SPLIT=… RUN=…」，4 題一批。
3. subagent 回報後跑 `record`。token 和秒數取自通知裡的 `subagent_tokens`／`duration_ms`，按批平均：`python -m arcagi.llm record ID aos/llm/responses/RUN/ID.json --split S --run RUN --model claude-opus-5-5 --tokens T --seconds X`
4. `python -m arcagi.llm rescore`，再 `summary --split S --run RUN --csv reports/llm-s2/RUN.csv`

## 坑

- 工作樹是和 S1、S4、S5 共用的。`git pull --rebase` 會因為別人沒 commit 的檔而被拒：改成先 `git fetch`，`HEAD..@{u}` 是空的就直接 push。add 時只 add 自己的路徑。
- `aos-llm` 只寫 `aos/llm/`，不寫 `aos/blocks/`。evaluation 題不落候選。
- 改 `solver.md`／`dsl.md` 會讓 `prompt_hash` 跟著變。evaluation 不可以拿來調提示。

## 下一步建議

- 把 [missing.csv](llm-s2/missing.csv) 裡重複出現的需求做成主線原語：物件原語可指定背景色、物件屬性 `n_holes`、顏色當變數的 `local_rule`。做完後重跑 eval20，看 LLM 解出的題數升不升。
- 剩下 280 題左右的 training 未解題，也可以照同樣流程大量跑，累積軌跡當蒸餾原料。
