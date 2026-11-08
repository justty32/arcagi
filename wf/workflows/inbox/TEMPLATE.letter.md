---
from: <寄件者名>
to: <收件者名>
status: <REQUEST | DONE | BLOCKED | NEEDS-USER | FAILED | PROGRESS>
at: <ISO 8601 含時區，如 2026-08-29T14:12:03+08:00>
reply-to: <我自己工作資料夾的 inbox 路徑；不需回信寫「不需回信」>
---
# <單獨看也能懂的一句結論>

## 做了什麼

<`REQUEST` 就寫「要對方做什麼」，指得越具體越好。>

## 產出（檔案路徑 / commit / 分支）

<沒有就寫「無」，別刪這段。>

## 沒做到、或證據不足的部分

<誠實寫。這段空著＝你沒想過，不是沒事。>

## 需要對方或使用者決定的事

<具體問題＋可選方案。>

<!--
複製本檔改寫，檔名 `<YYYYmmddTHHMM>-<寄件者>-<STATUS>.md`，放進**收件方的 `inbox/`**。
用 `tools/inbox_send.sh` 寄可自動產生檔名與 frontmatter，並原子投遞。
格式與 STATUS 語意見 PROTOCOL.md。信體投遞後別回頭改——要補就寄新的一封。
-->
