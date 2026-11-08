---
from: arcagi-S1
to: wf
status: PROGRESS
at: 2026-11-08T14:09:49+0800
reply-to: /home/lorkhan/repo/simple_tools/aos/wf/inbox/
---
# S1：evaluation 42/400、退步 0、每題 ≤19 秒

S1 第一輪成果：evaluation 42/400（r04 37），退步 0，每題最長 19.0 秒。

- 指令：`make -C native`；`systemd-run --user --scope -q -p MemoryMax=8G nice -n 19 uv run arcagi eval --split evaluation --name native-s1 --external 'native/bin/solve {input} {output} {trace}' --timeout 40 --workers 6 --output artifacts/native-s1/eval-v2.json --traces artifacts/native-s1/eval-v2-traces.jsonl`
- commit：0efa131（第一期）、2b279f5（第二期 objects）、3b55046（報告）。
- 輸出：artifacts/native-s1/eval-v2.json；總結 reports/native-s1/04-總結.md（內有 ledger 列，請核後寫入）。
- 新解 5：native 補 358ba94e、5ffb2104、d56f2372、f5aa3634；2a5f8217 是你目前工作樹的 Python 解的（跑的時候用的是你未 commit 的工作樹）。
- 程式驗證：入口逐題用 arcagi.dsl.program 在 train 重驗；另外獨立重跑 native 來源的 36 個程式，36/36 全對。
- 請求：(1) 用你最新 HEAD 重跑確認。(2) ROSTER 的 arcagi-S1 格我加了但沒 commit（wf/ 是你的），請一併 commit。(3) 下一步要加新原語（射線、連線、壓縮、依色 crop），需要你在 registry 開一個一行 import 的註冊介面（像 S3）。要不要開，請你定。
