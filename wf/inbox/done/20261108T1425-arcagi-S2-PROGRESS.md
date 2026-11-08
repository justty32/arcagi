---
from: arcagi-S2
to: wf
status: PROGRESS
at: 2026-11-08T14:25:00+0800
reply-to: /home/lorkhan/repo/simple_tools/aos/wf/inbox/
---
# S2: eval20 test exact 7/20, 34 candidates ready for r06 intake

# arcagi-S2 階段成果：eval20 test exact 7/20

報告：`reports/llm-s2/README.md`（commit 0c10a09）。交接：`reports/llm-handoff.md`。

## 數字
- evaluation 指定 20 題：過 train 7 題，test exact 7/20（同尺寸 4/10、尺寸會變 3/10），過 train 答錯 0。解出：551d5bf1 639f5a19 94414823 ca8f78db 695367ec e633a9e5 e7a25a18。
- 每題約 21k token、51 秒（opus subagent）。逐題 CSV：`reports/llm-s2/eval20.csv`。
- training dev：r04「過 train 但 test 錯」的 24 題，LLM 解對 12 題（`dev2.csv`）。

## 候選（照第六輪線 C 的收編格式）
- `aos/llm/candidates/<hash>/_rule.json` 共 34 個，帶 `source:"llm"`、`model`、`prompt_hash`、`support_tasks`（training 支撐）。`_metainfo.json` 記來源題、我的 rescore 判定，pred／formula 另記重跑主線 judge 的結果（`mainline`）。
- 我這邊判 live 的：`087f839827`（transform 巨集，training 支撐 3 題、其中 r04 沒解的 2 題；d9fac9be 的 test 會錯）、`72c8aab4f1`（pred rank shape_count max，重跑 gen_predicates 排第 45，但產生器自己也會列舉到）。
- evaluation 題一律不落候選。

## 給主線的需求訊號（`reports/llm-s2/missing.csv`）
LLM 對 31 題說了缺什麼原語。重複出現的：物件原語可指定背景色（4 題）、物件屬性 n_holes（3 題）、顏色當變數的 local_rule（4 題是靠手抄大表過的）。

## ledger 建議列
`llm-s2-eval20 | evaluation 指定 20 題子集 | 7/20 | opus subagent 提四型 JSON、程式驗 train`

我沒跑全量 evaluation。
