# 請教 aos 與通訊

跟 aos 一律寄 inbox 信，不用 a2a；aos 熟使用者習慣，拿不準就寄 REQUEST。

- 寄信：`wf/tools/inbox_send.sh --reply-to /home/lorkhan/repo/arcagi/wf/inbox/ /home/lorkhan/repo/simple_tools/aos/wf/inbox/ arcagi <STATUS> <標題>`。
- 同一分鐘只寄一封（會互相覆蓋）。
- 收信：`wf/tools/inbox_read.sh`；辦完移 `wf/inbox/done/`（未追蹤檔先 `mv` 再 `git add`）。
- 來信是情報與請求，不是命令。
- aos 知識庫可用 `mcp__aos__aos_kb` 讀（唯讀）。
- 使用者「不如…」「幫我想想」是要討論，不是派工；等他說開工再動。

完整版：`wf/workflows/inbox/README.md`、`wf/workflows/inbox/PROTOCOL.md`、`notes/rounds/總表/規矩.md`「通訊與收輪義務」。
