# N8c progress（03:2x 交棒）

- 單元：`arcagi-n8c-pipe.service`（systemd --user，MemoryMax=16G，nice 19）跑 `/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n8c/pipeline.sh`：
  codex 實作（timeout 80m）→ `make -C native hot-e` → `uv run pytest -q tests/native` → `reports/cpu-hot-1110/n8c_bench.sh /tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n8c/bench`
  （arcbatch / hot / hot-e 交錯 ×3，1e6 再 1e7，4 threads；05:00 後不開 bench、05:35 後不開新 run）→ analyze.py。
- 階段標記（都在 `/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n8c/`）：DONE-codex（含 rc）、DONE-build／FAIL-build、DONE-pytest（含 rc）、DONE-bench、**DONE**（全完）、
  SKIP-bench-late、STOPPED、bench/ABORT-deadline。log：codex.log、build.log、pytest-native.txt、bench.log、analyze.txt。
- 等：`until [ -e /tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n8c/DONE ] || ! systemctl --user is-active -q arcagi-n8c-pipe; do sleep 30; done`
- 判讀（一行）：
  `cat /tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n8c/DONE-* ; tail -3 /tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n8c/pytest-native.txt; cat /tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n8c/analyze.txt; grep -c ' 0/' /tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n8c/bench/cmp.txt; python3 -c "import re;t=open('/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n8c/analyze.txt').read();print([l for l in t.splitlines() if 'hot-e' in l or 'arcbatch-hot ' in l])"`
- 收不收：cmp.txt 全部 0 mismatches（hot 與 hot-e 對 arcbatch r1，1e6、1e7 各 3 次）＋ tests/native 全過 ＋
  hot-e 中位牆鐘相對 arcbatch-hot 在 **1e7 快 >2%**（1e6 不得變慢 >2%）才收；否則不收、arcbatch-hot 維持。標負載（bench.log／wall 的 loadavg）。
- 收完：把表與判讀補進 n8c.md「結果」節，連同 codex 改動（native/hot/、native/Makefile、tests/native/、n8c-impl.md）本機 commit；
  先 `git diff --stat native/src` 確認為空。05:40 前確認 `systemctl --user is-active arcagi-n8c-pipe` 為 inactive，否則 stop。
