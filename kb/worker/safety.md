# 安全邊界

寫入只限交接書給的範圍；不 sudo、不裝套件、專案內不 rm、不碰機密；STOP 檔在就停。

- 寫入：交接書寫的路徑（今晚上限 `~/repo/arcagi`、`~/code/playground-arc1`、session scratchpad）。其他唯讀。
- 不 sudo、不裝套件、不改系統與 LM Studio／litellm 設定、不 load／unload 模型。
- 專案內不 `rm`；丟棄物放 scratchpad 的線名子夾。
- 不讀 `~/.ssh`、keyring、瀏覽器資料、別專案 `.env`／金鑰。
- 對外只限本機 LLM 端點、agy／codex 自身連線；今晚不 push 不 pull。
- `ls ~/arcagi-STOP` 存在＝使用者喊停：停手、回報。
- `data/`、`vendor/` 預設唯讀；`AGENTS.md`、`wf/` hub 檔（INDEX、WORKFLOWS、SESSION-LOG、WAIT_USER）只有主 agent 能寫。
- 派孫 agent：本段原樣帶上。

出處：`notes/rounds/總表/規矩.md`「11-09 夜跑授權」安全邊界、`wf/workflows/dispatch/README.md`「領地登記」。
