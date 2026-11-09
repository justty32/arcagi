# codex 用法與坑

一律明帶 `-m gpt-6.1-sol -s <沙箱>`，提示第一行 `/goal <可驗證完成條件>`，任務書從 stdin 餵。

實作：
```
codex exec -m gpt-6.1-sol -s workspace-write -C <可寫夾> [--add-dir <另一夾>] \
  --color never -o <回報.md> '/goal <實際跑一遍、結果對>' < task.md > <log> 2>&1
```
蒐集用 `-s read-only`；`-o` 由 codex 本體寫，不受唯讀限制。

坑：
- 不帶 `-m`／`-s` 就是預設 terra＋danger-full-access。不用 astra。
- 會做到一半說完成 → 一定寫 `/goal`；續跑 `codex exec resume --last "<收尾提示>"`（resume 不吃 `-s`，唯讀用 `-c sandbox_mode='"read-only"'`）。
- 沙箱不能寫 `.git` → commit 由派它的 Claude 做。
- `-C` 非 git 夾加 `--skip-git-repo-check`；連 LiteLLM 加 `-c sandbox_workspace_write.network_access=true`。
- sol 程式能力差：diff 交 opus 審，越界改的還原。

完整版：`notes/rounds/gpu-night-1109/思考輪-流程.md` §2。
