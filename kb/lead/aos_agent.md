# 自起 aos 樹與只讀 agent

「讀檔→挑毛病」這類小事可交給 aos agent（luna，只 read／ls），14 秒、2 次呼叫一題；樹已在 `arcagi-aos-daemon.scope` 常駐。

- 樹：根 daemon 管總機（llm kernel→litellm）與領班（跑 agent）；全寫在 `.aos-run/`（gitignore）。
- 先確認活著：三台 `aos-daemon-ctl -d <stack> ping`；根 pid 看 `systemctl --user status arcagi-aos-daemon.scope`。
- 開 agent：`ctl add`→`tools add read/ls`→**`tools rm wall_clock self_tools agents memory`**→`llm set endpoint=luna`。
- 問：`aos-agent say … && aos-agent listen --timeout-s 600`；帳在 agent 的 `observed.jsonl` 與 `.aos-run/llm/ledger.jsonl`。
- 收：整棵 `kill -TERM <根 pid>`；單隻先複製 history 再 `ctl rm`。
- luna-low 答案中等，結論要人核。

完整版：`notes/rounds/gpu-night-1109/aos-daemon/食譜.md`（起／停／看門狗／坑）、`結果.md`（首跑數字與寫入邊界）。
