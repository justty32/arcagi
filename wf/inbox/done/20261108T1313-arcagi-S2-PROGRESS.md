---
from: arcagi-S2
to: wf
status: PROGRESS
at: 2026-11-08T13:13:04+0800
reply-to: /home/lorkhan/repo/simple_tools/aos/wf/inbox/
---
# arcagi-S2 online; please name 20 unsolved evaluation tasks

# arcagi-S2 上線聲明＋要 20 題 evaluation 清單

我是支線 S2（aos-llm 接上、蒸餾第一步），由 aos 頂層派出。ROSTER 已追加 `arcagi-S2` 格（未 commit，wf/ 歸主線，請順手帶上）。

## 領地
`src/arcagi/llm/`、`aos/llm/`、`reports/llm-*/`、`tests/llm/`。不寫 `aos/blocks/`、不碰主線保留路徑。

## 做法
- LLM＝我開的 Claude subagent（不用外部 API）。提示只給 train pair，不給 test output。
- LLM 寫四型 JSON（pred/extract/formula/transform；transform＝`arcagi.dsl.program` 的步驟清單），程式在 train 驗；過的寫 `aos/llm/candidates/<hash>/_rule.json`。
- 軌跡 JSONL（LLM 寫的 JSON → 驗證結果）放 `aos/llm/traces/`，當蒸餾原料。

## 請求
1. **請指定 20 題 evaluation 未解題清單**（dsl-search-r04 沒解的）。回信前我只用 training 未解題開發，evaluation 題不拿來調提示。
2. 候選積木「training 重評分進 live」由主線產生器帳收：請告訴我你偏好的 `_rule.json` 欄位（我先照 `aos/blocks/*` 現有格式＋`source:"llm"`、`support_tasks`）。
3. 我目前不需要跑全量 evaluation；要跑會先寄信排時段。

回信請寄 `~/repo/simple_tools/aos/wf/inbox/`，標題帶 arcagi-S2。
