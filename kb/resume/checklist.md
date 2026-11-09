# compact 後檢查表（摘要）

每次 compact 都做：看門狗、STOP、inbox、監看、排程、現役線、GPU；完整版在當夜看板。

完整版與當前數值：`notes/rounds/gpu-night-1109/README.md`「compact 後檢查表」。要點：

1. `systemctl --user list-units 'arcagi-*' --plain --no-legend`：`arcagi-watchdog` 要 active，掉了照 `scripts/watchdog_night.sh` 開頭註解重開。
2. `ls ~/arcagi-STOP`：存在＝使用者喊停，全停、不派新線。
3. `ls wf/inbox/`：頂層有信先辦，辦完移 `done/`。
4. Monitor／Cron 是 session 內的東西，compact 或重開會失效：照看板重開 inbox 監看、補排程（`CronList` 核）。
5. 看板「現役線」逐條確認；子 agent 回報照 dispatch 收線。
6. 每次 commit 後更新看板與 SESSION-LOG。
7. GPU 不准閒：`nvidia-smi --query-gpu=utilization.gpu,power.draw,temperature.gpu --format=csv`。
8. 拿不準的流程、偏好問 aos（見 `lead/ask_aos`），不自己猜。
