# WORKFLOWS — 工作流派發器

[INDEX](INDEX.md)｜結構 [STRUCTURE](STRUCTURE.md)

使用者要做事 → **從派發表選工作流 → 讀它的入口檔**；細節都在入口檔。

**可以跳流程**：單行或小範圍、低風險、不跨 session 的修正；純查詢或一次性回答，不留 durable 知識；使用者明確要求快速處理；既有工作流只會增加同步成本而不降低風險。跳流程不等於跳過工程規矩——仍要讀必要上下文、不破壞使用者改動、能測就測。

## 派發表

### 開發 flavor

碰原始碼的工作流共用 [common/conventions](workflows/common/conventions.md)（寫碼慣例）與 [common/code-map](workflows/common/code-map.md)（哪個檔負責什麼）。

| 觸發（你說…）| 工作流 | 入口檔（先讀這個）|
|--------------|--------|-------------------|
| 「開發 / 修改某個功能」「**修 bug**」 | **feature-dev** | [workflows/feature-dev/README.md](workflows/feature-dev/README.md) |
| 「跑測試 / 驗證」「這樣改有沒有壞」 | **testing** | [workflows/testing.md](workflows/testing.md) |
| 「重構 / 拆檔 / 整理結構」（行為不變）| **refactor** | [workflows/refactor/README.md](workflows/refactor/README.md) |
| 「搬檔案 / 改目錄名 / 拆 repo」 | **refactor**（搬移專章）| [workflows/refactor/moving-things.md](workflows/refactor/moving-things.md) |
| 「這個陌生專案是怎麼運作的」「幫我分析這個 repo」 | **analysis** | [workflows/analysis.md](workflows/analysis.md) |
| 「查清楚這是怎麼運作的」「這樣做可不可行」 | **investigation** | [workflows/investigation.md](workflows/investigation.md) |
| 「做一包 patch 給別的專案 / 別的 agent 套」 | **patch** | [workflows/patch.md](workflows/patch.md) |
| 「環境怎麼裝」「fresh clone 後要做什麼」「指令是什麼」 | **dev-env** | [workflows/dev-env.md](workflows/dev-env.md) |
| 「討論方案」「寫動工計畫」（spec / plan）| **planning**（kernel 管線的後兩段）| [workflows/planning.md](workflows/planning.md) |

**analysis** ＝初次接觸陌生專案、要建立可延續的分析產物；**investigation** ＝回答一個窄問題。**patch** ＝跨 repo、原專案無 git 或不能直接 push、要交給冷啟動 agent 套用時才用；同一個 repo 內能改能測就走 feature-dev。
### 知識工作 flavor

| 觸發（你說…）| 工作流 | 入口檔（先讀這個）| 分辨 |
|--------------|--------|-------------------|------|
| 「寫一篇東西：文章 / 筆記 / 文件 / 翻譯 / 貼文」 | **write** | [workflows/write.md](workflows/write.md) | 產物是**給人讀的成品** |
| 「幫我讀懂這份材料」「做個摘要」 | **digest** | [workflows/digest.md](workflows/digest.md) | 材料有限、讀完即止；產物是**摘要 + 出處索引** |
| 「規劃一件事：活動 / 旅行 / 流程 / 任意非開發專案」 | **plan-a-thing** | [workflows/plan-a-thing.md](workflows/plan-a-thing.md) | 產出**不是程式碼**（是的話走開發 flavor 的 spec / plan）|
| 「在幾個選項間做決定」 | **decide** | [workflows/decide.md](workflows/decide.md) | 問的是「**選哪個**」；問「要不要做」走 planning |
| 「學一個主題，建立可延續的筆記」 | **learn** | [workflows/learn.md](workflows/learn.md) | 主題開放、會回訪；產物是**可回訪的筆記樹**（digest 的升級形態）|
| 「整理一堆資訊 / 檔案 / 筆記的結構」 | **organize** | [workflows/organize.md](workflows/organize.md) | 動的是**位置與分類**，不是內容 |

例：「幫我讀懂統計檢定」——只要這次看懂 → digest；要持續學下去 → learn。想法要不要做、何時做（idea / roadmap）走 kernel 的 [planning](workflows/planning.md)。產出文字的工作流共用 [common/writing](workflows/common/writing.md)（文風）、材料導航共用 [common/info-map](workflows/common/info-map.md)。
<!-- wf-insert:WORKFLOWS -->

### kernel 內建

| 觸發（你說…）| 工作流 | 入口檔 |
|--------------|--------|--------|
| 「記 / 查踩坑」 | **gotchas** | [workflows/common/gotchas.md](workflows/common/gotchas.md) |
| 「整理 X」「封存過時的」「檔案太多／太雜」「太大要拆」 | **tidy** | [workflows/tidy/README.md](workflows/tidy/README.md) |
| 「記個想法」「以後要做」「排進 roadmap」「幫我規劃」 | **planning** | [workflows/planning.md](workflows/planning.md) |
| 「記個決定」「為什麼選 A 不選 B」 | **decisions** | [workflows/decisions.md](workflows/decisions.md) |
| 「我的偏好是…」「以後直接做 / 先問」 | **user** | [workflows/common/user.md](workflows/common/user.md) |

**都不符 → 看 [INDEX.md](INDEX.md)**。新開工作流 → 複製 [workflows/TEMPLATE.workflow.md](workflows/TEMPLATE.workflow.md) 並在上表加一列。要定期喚醒合 heartbeat 包、多 agent 協作合 multi-agent 包（都在模板 repo 的 `flavors/`）。

## 活狀態記哪裡（只列 open，完成即刪）

| 在等誰 | 記哪裡 |
|--------|--------|
| 等**使用者**做 / 驗證 / 決定 | [WAIT_USER.md](WAIT_USER.md) |
| 等**同 repo 另一個 session / fork** | [SESSION-LOG.md](SESSION-LOG.md) 一行 open |
| 等**別資料夾的 agent** | 信件軸：multi-agent 包提供（派發表有 inbox 才有）|
