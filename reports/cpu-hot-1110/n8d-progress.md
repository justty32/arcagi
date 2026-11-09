# N8d progress（03:42 交棒）

- 單元：`arcagi-n8d-pipe.scope`（systemd-run --user --scope，MemoryMax=16G，nice 19）跑 `/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n8d/pipeline.sh`：
  codex 實作 HOT_F（timeout 45m，任務書 `/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n8d/codex-task.md`）→ `make -C native hot-e hot-f` → `uv run pytest -q tests/native`
  → `n8d_bench.sh /tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n8d/bench`（arcbatch / hot-e / hot-f 交錯 ×3，1e6 再 1e7；05:08 後不開 bench、05:31 後不開新 run）→ analyze.py。
- 修改前快照：`/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n8d/seed_{enum,value}.cpp.before`。
- 階段標記（都在 `/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n8d/`）：DONE-codex（含 rc）、DONE-build／FAIL-build、DONE-pytest（含 rc）、DONE-bench、**DONE**、SKIP-bench-late、STOPPED、bench/ABORT-deadline。
  log：codex.log、build.log、pytest-native.txt、bench.log、analyze.txt；codex 回報 `reports/cpu-hot-1110/n8d-impl.md`。
- 等：`until [ -e /tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n8d/DONE ] || ! systemctl --user is-active -q arcagi-n8d-pipe.scope; do sleep 30; done`
- 判讀（一行）：`cat /tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n8d/DONE-*; tail -3 /tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n8d/pytest-native.txt; cat /tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n8d/analyze.txt; grep -c ' 0/' /tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n8d/bench/cmp.txt`
- 收件門：cmp.txt 全 0 mismatches（hot-e、hot-f 對 arcbatch r1，各 budget 3 次，含 eval_steps）＋ tests/native 全過 ＋
  hot-f 中位牆鐘對 hot-e **1e7 快 >2%** 且 1e6 不慢（>2% 算慢）才收；否則不收、hot-e 維持。
- 審 diff 重點：`git diff native/hot/seed_value.cpp` 的 eval() kid 迴圈——葉節點（CONST/INPUT/VAR/LAM）不扣步數、內部節點
  先 `--c.steps` 再走 kids、VAR 越界即 ERR、LAM 用 kid 節點 index；call() 的 A 快取記帳不動；`#ifndef HOT_F` 原碼逐字。
- 收完：結果表＋判讀補進 n8d.md，連同 native/hot/、native/Makefile、tests/native/、n8d-impl.md 本機 commit；
  先 `git diff --stat native/src` 確認為空。**05:35 前**確認 `systemctl --user is-active arcagi-n8d-pipe.scope` 為 inactive，否則 `systemctl --user stop arcagi-n8d-pipe.scope`。
