---
from: arcagi-S2
to: wf
status: PROGRESS
at: 2026-11-08T14:56:47+0800
reply-to: /home/lorkhan/repo/simple_tools/aos/wf/inbox/
---
# S2 第二任：s40 15/40、大表改寫 9/10、live 候選 2→8，缺原語分類表已出

# S2 第二任 PROGRESS：s40 拿到 15/40，大表改寫 9/10，live 候選從 2 個增加到 8 個

commit 6b6b485、73e87e5（已 push）。報告 reports/llm-s2b/README.md，交接 reports/llm-handoff.md。

## 數字
- s40：r05 沒解的 training 40 題，過 train 15、test exact 15、過 train 答錯 0。每題約 20.6k token、53 秒。
- gen1：之前靠手抄大表過的 10 題（表 16～1656 列），改寫成短規則（表 ≤8 列）。9/10 test 全對。a85d4709 有了短解。
- 候選：73 個。rescore 判 live 12 個，扣掉主線判 covered 的 4 個剩 8 個，都在沒見過的 training 題上有支撐。合成集過半的有 `05ade5e13a`（`x_connect hv`，4/4）和 `087f839827`（2/3）。`5aa214b429`（`x_period fill 0`，支撐 5 題）在合成集只有 1/5 過半，因為顏色寫死，應該算背答案。

## 給主線
1. 線 C 收編時，S1 的 `x_*` 原語包成 macro 之後，Python search 才拿得到（`PYTHON_SEARCH=False`）。
2. 缺原語前 5 名：線與射線變體 9 題、可指定背景或補邊顏色 7 題、排序／排版 7 題、蓋模板 6 題、修補後裁回洞的 bbox 3 題。分類表在 reports/llm-s2b/missing.csv，每列都標了建議給 S1、S3 還是主線。
3. 蒸餾時看到的新訊號（建議給 S1）：旋轉封閉的局部規則（6 題都寫成同一張表 × rot90 四次）、local_rule 的鄰居萬用字元、pad／unpad、x_period 的洞色改吃 extract。

## 還沒做（下一任）
- search A/B：加進片段積木後 training 多解哪些題、退步幾題。工具 `python -m arcagi.llm distill` 已經寫好，等你們全量跑完才跑。全量照規矩：nice、workers 6、MemoryMax=8G。
- S1、S3 做完後重跑 eval20（dsl.md 已經加進 x_vrule 等原語）。
