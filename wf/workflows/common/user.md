# user — 使用者偏好與確認邊界

[common/README](README.md)

agent 不用重猜的事。always-on 鐵律在 AGENTS.md，這裡是**這位使用者**的偏好——改了改這裡，不改鐵律。

**何時用**：使用者說了偏好、講定了確認邊界（哪些事可以直接做、哪些一定先問）、或講定分支慣例／時區／語言時，記到這裡。
**何時不用**：一次性的小事不必記（例如「這次先不要跑測試」）——那是當下的指示，不是長期偏好；長期知識歸屬層的原則見 [STRUCTURE](../../STRUCTURE.md)。

## Done when

對應的那一列已更新（或新開一列），沒有留下與新偏好矛盾的舊值。

| 項目 | 設定 |
|------|------|
| 語言 | 回覆與文件繁中；程式碼註解、docstring、commit 訊息英文 |
| 分支慣例 | 單一分支，直接 commit main（push 仍依鐵律 2）。**2026-11-08 使用者授權：可隨意 push**（鐵律 2 的授權來源）|
| 直接做、不用問 | 改 `wf/` 內文件、加測試、跑唯讀指令與 pytest／評測 |
| 一定先問 | 刪檔、新增／升級依賴、下載大型資料或模型、動 `data/` 內容（push 與對外動作依鐵律 2）|
| 回覆風格 | 通用風格見 [reply-style.md](reply-style.md)；這位使用者的例外：（尚無）；使用者問「要不要」時附**可執行判準**（門檻數字）與後果，讓他能改數字 |
| 時區 | Asia/Taipei |
| 子 agent 分工 | 2026-11-08：普通工作 opus、簡單與雜活 sonnet；先讀 `wf/` 規矩（雜活除外）；可再派、模型隨意 → [team-model](../team-model.md) |
| 子 agent 分工補充 | 2026-11-09：實作、寫檔等普通文字處理優先交 codex gpt sol（`-m gpt-6.1-sol`，必帶 `-s`；除 astra 外型號皆可）或 litellm sol；Claude 子 agent 留給設計、審查、驗收；設計用 fable、審稿 agy Argon。子孫 agent 要做權限管理（交接書帶安全邊界段、原樣下傳）與 context 管理（一線一里程碑；context 約 30% 就寫 progress 交接換手）|
| 長時間無人值守 | 2026-11-09：使用者會設 goal＋auto compact（30% 觸發）；主 agent 把續行點寫進 SESSION-LOG 與當夜看板，compact 後照看板檢查表恢復（看門狗、停止開關 `~/arcagi-STOP`、inbox 監看、排程）|

## aos 累積的習慣速查

aos 頂層 11-09 整理、跟本表不重複的使用者習慣（睡時不問改放看板、起床報告格式、講人話、「不如…」是討論不是派工、sol 碼要 opus 審、每段派人試玩…）→ [user-aos習慣速查](user-aos習慣速查.md)。衝突以本表為準。

## 外出時

使用者常長時間外出、由多個 agent 分工。大小決策由主 agent 先代定、不停線等他；**代定清單**記在 [SESSION-LOG](../../SESSION-LOG.md)（或該輪紀錄），他回來時用白話報告做了哪些決定、在哪翻案；非他拍板不可的進 [WAIT_USER](../../WAIT_USER.md)。沿用他在 aos 定的做法（2026-10-09）。

## 長期記憶放哪

值得跨 session 留下的偏好、規矩、坑、決定一律寫進 `wf/` 對應檔，不寫 agent 工具的自動記憶。沿用他在 aos 定的做法（2026-09-30）。

領域詞彙常猜錯 → 開 `glossary.md`（見 [common/README](README.md)）。
