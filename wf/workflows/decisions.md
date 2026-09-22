# decisions — 決策記錄（為什麼選 A 不選 B）

[WORKFLOWS](../WORKFLOWS.md)｜[INDEX](../INDEX.md)

留下「為什麼」：git log 找得回改了什麼，找不回**為什麼放棄方案 C**。

**何時用**：在兩個以上可行方案裡選一個，且日後可能被問「當初為什麼」。
**何時不用**：只有一條路，或隨時可回頭的小事。決策過程要結構化評估 → knowledge 包的 decide 工作流，結論再落到這裡。

## Done when

- 下表新增一列，且「未選方案與原因」「前提」兩欄非空。

## 記錄（新的在上）

| 日期 | 決定 | 未選方案與原因 | 前提（變了就重看）|
|------|------|---------------|-----------------|
| 2026-09-22 | 依賴與虛擬環境用 `uv`，lint／format 用 `ruff` | `pip + venv + requirements.txt`：沒有 lockfile，重現性差；`poetry`：比 uv 慢、多一層設定。**導入時 agent 代選，使用者尚未確認** | 專案是純 Python；使用者沒有指定工具 |
| 2026-09-22 | ARC-AGI-1 資料集以 git submodule 掛在 `data/ARC-AGI/` | 直接 commit JSON 進 repo：800 題檔案雜訊多、追不到上游更新；每次下載：離線就沒資料 | 上游 `fchollet/ARC-AGI` 仍公開可拉 |
| 2026-09-22 | 工作流用非侵入式導入（頂層只留 `AGENTS.md`／`CLAUDE.md`／`.claude/`，其餘在 `wf/`），flavor 取 dev＋knowledge | 標準佈局：頂層會多十幾個 `.md`，跟之後的 `src/`、`data/` 混在一起 | 模板 kernel v0.6 |

