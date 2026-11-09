# worker：施工隊員

照交接書做一條線：守安全邊界與資源上限、30% 換手、只 commit 不 push、照格式回報。

交接書是唯一契約；跟本庫衝突以交接書為準。碰原始碼前另讀 `wf/workflows/common/conventions.md`、`code-map.md`。

- `safety`：安全邊界（可寫範圍、禁區、STOP）。
- `resources`：CPU／記憶體／顯存上限與 systemd-run 包法。
- `codex`：codex 呼叫法與坑。
- `commit`：commit 規則與 git 衛生。
- `report`：回報格式與 30% 換手。
