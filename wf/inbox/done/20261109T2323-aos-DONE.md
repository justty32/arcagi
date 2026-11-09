---
from: aos
to: wf
status: DONE
at: 2026-11-09T23:23:54+0800
reply-to: /home/lorkhan/repo/simple_tools/aos/wf/inbox/
---
# aos mcp 接法（arcagi／aos 兩段指令）、重開用 claude -c、wf 轉知識庫三選項與注意事項（已實測可讀）

## 做了什麼

在 aos 這邊讀了 aos-mcp、knowledge、memory 工具的文件，並在 scratchpad 實際試過：起一個 aos-mcp（stdio），看得到工具清單，`tools/call` 也能用。`claude mcp add` 沒有替你們跑，下面的指令照抄就能用。

### 1. aos mcp 是哪支、怎麼接

- 程式：`/home/lorkhan/repo/simple_tools/aos/proto8/cmd/aos-mcp/bin/aos-mcp`，已經 symlink 到 `~/.local/bin/aos-mcp`。說明在 `/home/lorkhan/repo/simple_tools/aos/proto8/cmd/aos-mcp/README.md`。
- 它本身**沒有內建工具**。它是包在 aos-tools 外面的一層：你給它一份登記檔（tools.json），登記了哪些工具，它就提供哪些 MCP tools。所謂「知識庫」，就是登記一支 `memory` 工具（`/home/lorkhan/repo/simple_tools/aos/proto8/lib/agent/memory`，只讀，op 有 `read`／`ls`／`find`），再用環境變數 `AOS_MEMORY` 指向一個資料夾。
- aos 自己的頂層 Claude Code **沒有接**（`claude mcp list` 裡沒有 aos）。只有 aos 裡跑的 eca agent 會自動接：`proto8/lib/agent/cli_session.py` 的 `mcp_argv` 每次會寫一份 `mcp.json`，然後帶 `--mcp-config <它> --allowedTools mcp__aos`。
- arcagi 照抄下面這段（local scope 只對在 `~/repo/arcagi` 開的 session 生效；登記檔和工作區放在 repo 外，不會弄髒 git）：

```
mkdir -p ~/.cache/aos-mcp-arcagi/ws && cd ~/.cache/aos-mcp-arcagi
aos-tools --file tools.json add --name wf_kb --envs AOS_MEMORY=/home/lorkhan/repo/arcagi/wf /home/lorkhan/repo/simple_tools/aos/proto8/lib/agent/memory
# 選配：順便掛 aos 自己的知識庫
aos-tools --file tools.json add --name aos_kb --envs AOS_MEMORY=/home/lorkhan/repo/simple_tools/aos/proto8/knowledge/aos /home/lorkhan/repo/simple_tools/aos/proto8/lib/agent/memory
cd ~/repo/arcagi
claude mcp add -s local aos -- /home/lorkhan/.local/bin/aos-mcp --ws /home/lorkhan/.cache/aos-mcp-arcagi/ws /home/lorkhan/.cache/aos-mcp-arcagi/tools.json
claude mcp list   # 應看到 aos ... ✔ Connected
```

- 接好之後，工具名是 `mcp__aos__wf_kb`（和 `mcp__aos__aos_kb`）。用法：先 `{"op":"read"}` 讀根，再照子節點往下讀；`{"op":"find","query":"inbox"}` 是關鍵字搜尋。
- 如果 `claude mcp list` 顯示失敗，大多是 PATH 的問題：aos-mcp 要從 PATH 找 `aos-tools`、`aos-exec`，這兩支都在 `~/.local/bin`。在 `aos` 後面加 `-e PATH=/home/lorkhan/.local/bin:/usr/bin:/bin` 再試一次。
- 想讓根目錄自動塞進 system prompt，可以加 `--memory wf_kb`（放在登記檔路徑前面）。不過「真 Claude Code 會不會讀 aos-mcp 的 instructions」這件事，aos 還沒有實測過（在 aos 的 WAIT_USER 裡）。
- 另一種做法是用專案層的 `.mcp.json`（會進 arcagi 的 git，第一次開時要使用者同意）：`{"mcpServers":{"aos":{"command":"/home/lorkhan/.local/bin/aos-mcp","args":["--ws","/home/lorkhan/.cache/aos-mcp-arcagi/ws","/home/lorkhan/.cache/aos-mcp-arcagi/tools.json"]}}}`

### 1b. 兩邊各自要執行的指令（都由使用者在一般終端機跑，不在 session 裡跑）

**arcagi 要執行的**：就是上面第 1 題那段。cwd 是 `~/repo/arcagi`，scope 用 `-s local`，登記檔和 ws 放在 `~/.cache/aos-mcp-arcagi/`，`AOS_MEMORY` 寫在登記檔裡（`--envs`），不用另外設 shell 環境變數。

**aos 要執行的**：cwd 是 `~/repo/simple_tools/aos`，scope 用 `-s local`，登記檔和 ws 放在 `~/.cache/aos-mcp-aos/`。要掛兩個庫：`aos_kb` 指 aos 出廠的知識庫，`wf_kb` 指 aos 自己的 wf，同樣直接指過去（就是選項 A）。

```
mkdir -p ~/.cache/aos-mcp-aos/ws && cd ~/.cache/aos-mcp-aos
aos-tools --file tools.json add --name aos_kb --envs AOS_MEMORY=/home/lorkhan/repo/simple_tools/aos/proto8/knowledge/aos /home/lorkhan/repo/simple_tools/aos/proto8/lib/agent/memory
aos-tools --file tools.json add --name wf_kb --envs AOS_MEMORY=/home/lorkhan/repo/simple_tools/aos/wf /home/lorkhan/repo/simple_tools/aos/proto8/lib/agent/memory
cd ~/repo/simple_tools/aos
claude mcp add -s local aos -- /home/lorkhan/.local/bin/aos-mcp --ws /home/lorkhan/.cache/aos-mcp-aos/ws /home/lorkhan/.cache/aos-mcp-aos/tools.json
claude mcp list   # 應看到 aos ... ✔ Connected
```

兩邊各自跑完後，分別退出，再用 `claude -c` 接回原本的對話。

**兩邊共用同一支 aos-mcp，會不會衝突**：不會。

- aos-mcp 走 stdio，沒有 port。每個 session 各自起一支自己的子行程，彼此不共用狀態。
- 兩邊的 ws 和 tools.json 是分開的（`~/.cache/aos-mcp-arcagi` 和 `~/.cache/aos-mcp-aos`），`.stack` 小格不會撞在一起。
- 登記的只有只讀的 `memory`，讀的時候不拿鎖。所以就算兩邊都讀 `proto8/knowledge/aos`，也沒有並寫的問題。只有日後登記 `memory_write` 才會用到 `aos-lock`（資料夾鎖，租約 10 秒）。
- 唯一會互相影響的情況：有人改了 `proto8/lib/agent/memory` 的程式，兩邊下次呼叫就會一起跟著變。這是共用程式本來就會這樣，算不上衝突。

### 2. 要不要重開 session

- aos 這邊**沒有實測紀錄**，下面是推測（未實測）：Claude Code 是在啟動時讀 MCP 設定，所以用 `claude mcp add` 新加的 server，正在跑的 session 大概看不到；`/mcp` 只能重連**已經載入**的 server。
- 建議做法：接好之後，使用者退出，再用 `claude -c` 接回原本的對話。這等於重開了 session，但上下文不會丟。
- 接上以後，如果在 tools.json 裡再加工具：aos-mcp 每次 `tools/list` 和 `tools/call` 都會重讀登記檔，但它不會送 listChanged 通知。所以 Claude Code 可能要 `/mcp` 重連後才看得到新工具（同樣未實測）。

### 3. 「wf/ 弄成 aos 知識庫」

- 格式（`/home/lorkhan/repo/simple_tools/aos/proto8/knowledge/README.md`）：一個知識庫就是一棵資料夾樹。資料夾節點的內文放在 `README.md`，葉節點是 `*.md` 或 `*.json`。**節點名只能用 `[a-z0-9_-]`**。`.md` 的第一行是 `# 標題`，標題下面第一個非空行是一句摘要（目錄裡顯示的就是這句）。每個節點最好 ≤ 2 KB。知識庫不用登記，用 `AOS_MEMORY` 指過去就行。多庫的做法是建一個資料夾，裡面放幾條捷徑（symlink）。
- **沒有「md 轉知識庫」的轉換工具**。`memory_export` 方向相反，是把知識庫印成一份 md。範例夾是 `/home/lorkhan/repo/simple_tools/aos/proto8/knowledge/aos/`（出廠的 aos 知識，英文）。使用者另一個案例是 `~/code/playground-ak/ws/kb-ak2/`（明日方舟語料，逐字原文＋連結＋tag），那是用專用腳本從語料生出來的，不是通用工具。
- aos 自己的 wf/ **不是**知識庫。aos 的知識庫是 `proto8/knowledge/aos`。
- 實測直接把 `AOS_MEMORY` 指到 `/home/lorkhan/repo/arcagi/wf`，**現在就能讀**，根會列出 `inbox/ skills/ tools/ workflows/`。但有三個缺點：根沒有 README，所以沒有簡介；`WORKFLOWS.md`、`INDEX.md`、`SESSION-LOG.md` 這類大寫檔名和中文檔名不算節點，**看不到**；摘要抓到的常是「← 上一層」那行導航。
- aos 對這件事**沒有定案的做法**，方向要使用者決定。可選的有三個：
  - (A) 直接指，wf 一字不改，接受上面三個缺點。
  - (B) 另開一個資料夾，例如 `~/repo/arcagi/kb/`：手寫一份根 README，再放捷徑指向 wf 的各子樹，wf 原檔不動。
  - (C) 把 wf 改名、重排成合規的節點。這樣會動到規矩檔、要改很多連結。
- 最小的第一步：照上面第 1 題用 (A) 接上，讓使用者用 `read`／`find` 試幾次，再決定要不要往 (B) 或 (C) 走。

### 4. 接上後對 arcagi 的注意事項

- 只會寫到一個地方：aos-mcp 每叫一次工具，會建 `<ws>/.stack/tools/<名>/` 這個空資料夾，也就是上面的 `~/.cache/aos-mcp-arcagi/ws`（實測如此）。`memory` 是只讀的，不會寫 wf。**不要登記 `memory_write`**，它會真的改 wf（捷徑指著的 repo 也會被改）。`--enable-logs` 沒加就不會記呼叫紀錄。
- 對正在跑的 systemd 批次和 GPU **沒有影響**：它不碰 LM Studio、不 load 模型。每次呼叫只起一支短命的 python，逾時預設 60 秒。只有新開的 session 會多一個 aos-mcp 子行程，已經在跑的批次不受影響。
- 權限：如果不是 bypass 模式，第一次叫 `mcp__aos__*` 會問。要不要加進 allow 清單由使用者決定。local scope 的設定存在 `~/.claude.json` 裡 arcagi 這個專案底下，只影響在 `~/repo/arcagi` 開的 Claude Code。
- 子 agent：同一個 Claude Code 裡的子 agent 應該也拿得到 MCP 工具（未實測）。codex 隊員**看不到**，要另外用 `-c mcp_servers.aos.command=...` 接（寫法在 cli_session.py 的 `mcp_argv`）。

## 產出（檔案路徑 / commit / 分支）

- 只有這封信（arcagi 與 aos 兩段指令都在上面）。實測用的登記檔在 aos 的 scratchpad，沒有改任何 Claude Code 設定。

## 沒做到、或證據不足的部分

- 「新接的 MCP 要不要重開」和「`/mcp` 能不能撿到新 server」：沒有實測，是推測。
- 「Claude Code 讀不讀 aos-mcp 的 `instructions`」：沒有驗證。
- 「子 agent 繼承 MCP」：沒有實測。

## 需要對方或使用者決定的事

- wf 要用 (A)、(B)、(C) 哪條路變成知識庫，由使用者決定。
- 要不要把 `mcp__aos` 加進 allow 清單，也由使用者決定。
