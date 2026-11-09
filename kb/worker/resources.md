# 資源限制

批次一律 systemd-run 掛單元、nice、限記憶體；顯存 ≤12GB；全機一條全量 eval。

- 包法：`systemd-run --user --scope --unit=arcagi-<線>-<名> -p MemoryMax=16G nice -n 19 <指令>`（長跑可不加 `--scope` 改背景服務）。
- CPU worker ≤12；單批記憶體 ≤16GB；swap 只有 512MB。Python 跑 1M 節點時減 worker（6 個會超 8G）。
- 顯存 ≤12GB（RTX 5060 Ti 16GB；nvcc 在 `/opt/cuda/bin`）；溫度 ≤85°C。
- 全量 eval 同時只一條：開跑前 `pgrep -af "arcagi eval"`；沒授權就只跑 `--task`／tag 小集合。
- 長跑交 systemd 背景，不在 context 裡等。
- 停：`touch ~/arcagi-STOP` 全停；`scripts/arcagi_stop_all.sh` 連看門狗一起停。
- LM Studio 只用已載入模型；本地 LLM 需求優先 litellm luna／terra。

出處：`notes/rounds/總表/規矩.md`「防當機限制」「LLM 資源」；環境指令 `wf/workflows/dev-env.md`（`uv run pytest -q`）。
