# N9b 進度（跑中交棒用）

- 開關 commit：0eaf09d（`ARCAGI_HYBRID_DEADLINE` 預設 19、`ARCAGI_GATED_TIMEOUT` 預設 60）。
- 單元：`arcagi-n9b-sweep.scope`（`reports/nodecap-1110/n9b_sweep.sh`，依序 d19→d40→d55→d120，workers 6，內建 05:38 截止與 `~/arcagi-STOP` 檢查；預估超過截止的組自動跳過）。
- 母體：`reports/nodecap-1110/n9b-tasks.txt`（188 題＝r07 training 中 out_of_budget 且 abstained）。
- 輸出目錄：`/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n9b/out/`（`d{D}-traces.jsonl`、`d{D}.json`、`sweep.log`）。
- DONE 檔：同目錄 `DONE`。
- 等：`until [ -e /tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n9b/out/DONE ] || ! systemctl --user is-active -q arcagi-n9b-sweep.scope; do sleep 30; done`
- 判讀（一行）：`.venv/bin/python reports/nodecap-1110/n9b_analyze.py /tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n9b/out`
- 下一步：把表貼進 `reports/nodecap-1110/README.md` 的 N9b 段，commit。evaluation 不跑。
