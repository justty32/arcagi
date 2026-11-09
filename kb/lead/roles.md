# 分工與模型

普通工作 opus、雜活 sonnet、實作與普通文字交 codex sol、設計 fable、審稿 Argon。

- 使用者 11-08：普通工作 opus、簡單與雜活 sonnet；子 agent 可再派、模型自選。
- 使用者 11-09：實作、寫檔等普通文字處理優先交 codex `gpt-6.1-sol`（必帶 `-m`、`-s`；astra 以外型號皆可）或 litellm sol；Claude 子 agent 留給設計、審查、驗收。
- 改寫使用者概念或規範條文**不算簡單工作**，不派 sonnet／sol。
- sol 寫的碼一定要 opus 審 diff，越界改的檔還原。
- 頂層線（主 session 直接派的）同時 ≤3；孫 agent 不算。
- 頂層不親手做事，能一句話交出去就交。
- 全機同時只一條全量 eval：開跑前 `pgrep -af "arcagi eval"`。

出處：`wf/workflows/common/user.md`「子 agent 分工」兩列、`wf/workflows/team-model.md`、`wf/workflows/common/user-aos習慣速查.md` C 段、`notes/rounds/總表/規矩.md`。
