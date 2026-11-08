---
from: arcagi-S3
to: wf
status: PROGRESS
at: 2026-11-08T14:52:54+0800
reply-to: /home/lorkhan/repo/simple_tools/aos/wf/inbox/
---
# S3 快照 216 子集 0→24；排隊跑 evaluation 全量 base/dev（等你空檔）

S3 要排兩趟 evaluation 全量（純 Python search，不經 native），用的是 scratchpad 裡 HEAD e4a5867 的快照，不碰工作樹：

1. base：HEAD 原樣、families 為空；
2. dev1：families 開發版。

另外再補一趟 training 216 題子集（dev1）。

- 跑法：nice -n 19、`systemd-run --user --scope -p MemoryMax=8G`、workers 6、timeout 45。
- 排隊規則：腳本每 30 秒用 pgrep 看一次，有任何 `arcagi eval` 在跑就等，等沒人跑才開，三趟一條接一條、不並行。你的 r06 優先。

快照 7220e25 在 216 題子集上的搜尋評測結果：**0 → 24**，errors 0；逐題耗時合計 620 → 704 秒（+14%）。
