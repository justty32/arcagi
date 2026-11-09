# 任務：<動詞開頭的一句話>

> 複製本檔改寫成一份交接書：同機子 agent 直接當 prompt；跨資料夾的存檔後用 inbox 寄出。派線規則見 [dispatch](dispatch/README.md)、派哪級模型見 [team-model](team-model.md)。
> **交接書是唯一契約**：沒寫在裡面的授權等於沒有；沒寫的禁區等於允許。

## 先讀規矩

開工前先 read 知識庫 `kb/worker`（施工線）或 `kb/lead`（會再派線的隊長）→ 本任務對應的工作流入口檔；細節或衝突才去讀 wf 原檔（`AGENTS.md` → `wf/WORKFLOWS.md` → `wf/workflows/common/user.md`；碰原始碼另讀 `wf/workflows/common/conventions.md`、`code-map.md`）。**雜活**（單純搬資料、跑一支指令回報輸出）可刪掉本段。
讀法：`echo '{"op":"read","path":"worker"}' | AOS_MEMORY=/home/lorkhan/repo/arcagi/kb python3 /home/lorkhan/repo/simple_tools/aos/proto8/lib/agent/memory/_entry`（或直接看 `kb/worker/README.md`）。

## 背景與唯一目標

<為什麼要做，以及**一個**目標。兩個以上的目標＝該切成兩條線。>

## 工作

1. <步驟>
2. <步驟>

## 硬性限制

- **可寫範圍**：`<路徑清單>`；**禁區**：`<不得寫的路徑>`（預設 `data/`、`vendor/` 唯讀）。
- **資源**：`<能否跑全量評測；不能就寫只准 --task／tag 篩的小集合>`。
- **commit／push**：`<不 commit｜commit 不 push｜commit 並 push>`（授權依 [user](common/user.md)；沒寫就不 commit）。commit 訊息英文，結尾署名照抄：`<署名行>`。
- **暫存與丟棄物**：放 scratchpad 裡 `<線名>/` 子資料夾；**不要 `rm`** 專案內的檔。
- **上限**：`<件數或時間上限>`，觸發就停下來回報，不自行擴大範圍。
- **可否再派子 agent**：`<可以，模型自選｜不可>`。

## 交付

| 產物 | 路徑（絕對路徑）|
|------|----------------|
| <是什麼> | `<絕對路徑>` |

## 驗收（條數寫死，不要自行加碼）

1. <可觀察條件：檔案存在／指令回傳／表格填滿>
2. <跑分線：完整指令、commit、`correct/total, errors`、輸出檔路徑>

**就這 N 條，不要做「其他你認為必要的驗證」。**

## 完成／阻塞回報（必做）

- 同機子 agent：最後一則訊息就是回報，開頭寫終局狀態 `DONE`／`BLOCKED`／`NEEDS-USER`／`FAILED`，接一句自足結論，再列交付與驗收逐條結果。
- 跨資料夾：`wf/tools/inbox_send.sh <上游 inbox 路徑> <線名> <STATUS> '<一句自足結論>' [正文檔]`，格式見 [inbox/PROTOCOL](inbox/PROTOCOL.md)。
- 卡住超過 10 分鐘先回 `BLOCKED`（需使用者決定用 `NEEDS-USER`），不可無聲等待。

> 送出前對照一次「背景與唯一目標」和「工作」有沒有互相矛盾——衝突處寫死哪個為準。
