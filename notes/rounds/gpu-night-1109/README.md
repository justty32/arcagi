# gpu-night-1109 — 夜跑看板（compact 後先讀這裡）

← [交棒總表](../README.md)｜授權與安全邊界 [總表/規矩](../總表/規矩.md)「11-09 夜跑授權」｜原信 [00-REQUEST](00-REQUEST.md)

## 目標（使用者 11-09 22:5x）

到 11-10 06:20 使用者起床前不停。順序：① 系統安全 ② 推進 aos 體系改進（非解題率）③ 多用 CUDA/GPU 做符號運算（GPU 擬合、遺傳符號回歸、符號＋神經混合）④ 每完成一輪大的改進就跑一輪思考設計輪（不按鐘點）（gpt sol 蒐集 → opus 匯總 → fable 設計＋agy Argon 審 → opus 細化 → gpt sol 實作）。

## 重開（resume）後先做（23:5x 為接 aos mcp 重開）

aos mcp 已接（local scope，`mcp__aos__wf_kb`、`mcp__aos__aos_kb`，只讀；設定說明 [aos-回信-mcp](aos-回信-mcp.md)；wf 轉知識庫走 (A) 直接指，B/C 待使用者定）。重開前所有 Claude 子 agent 已停，session 內排程與監看全失效，重開後：
1. 試一次 `mcp__aos__wf_kb` `{"op":"read"}` 確認可用。
2. 重開 inbox 監看、GPU 閒置警報 Monitor。
3. CronCreate 重排：`37 0 10 11 *` N3 第 3 棒（等 bench/FILLED，寫結論＋白話）；`4 6 10 11 *` 晨報＋待 push 清單＋寄 aos DONE。若已過 00:37 就直接做 N3 第 3 棒。
4. 派一條 opus 線把 wf 做成分層知識庫（走 B：`kb/` 根 README＋捷徑＋各層摘要，讓「主 session 恢復」「派工隊長」「施工隊員」各有一層入口；wf 原檔不動），之後交接書改成「先 read 知識庫某層」。使用者原話見 wf/workflows/common/user.md「aos mcp 知識庫」。
5. 派接手：T1 補 04 總結（think-1/progress.md）；N4b 照 reports/task-features-1109/progress.md 5 步做 gpuprofile；之後開思考輪 2（主題：使用者 11-09 夜建議 1～8＋T1 的下一輪反省點）。頂層 ≤3。

## compact 後檢查表（每次都做）

0. 先讀分層知識庫 `kb/resume/`（`cd ~/repo/simple_tools/aos/proto8 && echo '{"op":"read","path":"resume"}' | AOS_MEMORY=/home/lorkhan/repo/arcagi/kb python3 lib/agent/memory/_entry`，或直接讀 kb/resume/*.md）。

1. `systemctl --user list-units 'arcagi-*' --plain --no-legend`：`arcagi-watchdog` 必須 active；掉了就照 scripts/watchdog_night.sh 開頭註解重開（`systemd-run --user --unit=arcagi-watchdog --nice=10 /home/lorkhan/repo/arcagi/scripts/watchdog_night.sh`）。
2. `ls ~/arcagi-STOP`：存在＝使用者喊停，全停、不派新線。
3. `ls wf/inbox/`：頂層有信先辦，辦完 `git mv` 進 done/（注意未追蹤檔用 `mv` 再 `git add`）。
4. inbox 監看 Monitor（每 15 秒 `find wf/inbox -maxdepth 1 -name '*.md'`，30 分鐘到期要續）——compact 後若沒在跑就重開。
5. CronList 看 06:04 晨報排程在不在；不在就 CronCreate `4 6 10 11 *` one-shot（內容：核各線 overnight-summary、寫 晨報.md、寄 aos DONE）。
6. 下表「現役線」逐條確認狀態；子 agent 完成通知來了就照 dispatch 收線（對證據）並更新本表。
7. 每次 commit 後更新本表與 SESSION-LOG（**今晚只 commit、不 push**）。
7b. `systemctl --user is-active arcagi-aos-daemon.scope`：掉了先 `systemctl --user stop arcagi-aos-daemon.scope` 再照 aos-daemon/食譜.md 起。
8. **GPU 不准閒**（使用者：「不要讓gpu閒下來，一整個晚上我都要靠它取暖」）：`nvidia-smi --query-gpu=utilization.gpu,power.draw,temperature.gpu --format=csv`；功耗長時間 <100W 或 util 掉下來就加 GPU 負載（開新的 GPU 搜尋長跑或加大 batch），溫度 ≤85°C。
9. aos 頂層熟使用者過去習慣：拿不準的流程、偏好、過去 thinking 就寄 REQUEST 問它（`wf/tools/inbox_send.sh --reply-to ... aos inbox ... REQUEST`），不自己猜。

- **aos 自主**（使用者睡前）：「你可以自己起aos daemon，自己開aos agent，自己改進自己的工作流」→ 可自起 aos daemon（包 systemd-run arcagi-aos-*）、開 aos agent、改 wf/ 與 kb/ 工作流；安全邊界不變。

## 子 agent context 管理（使用者 22:5x「子agent的context也要做管理」）

- 一條線＝一個里程碑；交接書寫死**交棒點**，到點就寫進度檔（`<產物夾>/progress.md`：做到哪、數字、下一步、關鍵路徑）並回報 `DONE`／`PARTIAL`，由主 agent 開新線接力，交接書只帶上一段產物路徑、不帶對話。
- 子 agent 讀大檔、掃大量報告、跑長輸出一律派孫 agent 或用 grep／head，只把結論帶回；長跑交 systemd 背景，不在 context 裡等。
- **30% 換手**（使用者 22:5x）：「子agent的context也要管理，當他們到30%的時候就要讓他們寫交接，換手了」→ 子孫 agent 估計 context 用到約 30%（粗估：累積讀進／產出約 60k tokens，或工具呼叫約 40 次）就停手寫交接（`progress.md`：做到哪、數字、下一步、關鍵路徑、在跑的背景單元），回報 `PARTIAL`；上一層開新 agent 從 progress.md 接手。交接書都要寫明這條並原樣下傳。
- 孫 agent 同樣適用；回報只給結論＋路徑，不貼原始輸出。

## 分工

- **今晚不 push**（使用者 23:4x）：「今晚都不要push吧，就在我醒來前十分鐘準備好要push的東西(注意不要太大太多)，我醒來後再push。」→ 只本機 commit、不 push 不 pull；06:10 前整理好待 push 清單（commit 數、總大小、有無大檔），晨報附上，等使用者醒來 push。覆蓋上方「可隨意 push」。

- **git 衛生**（使用者 23:3x）：「節點池會膨脹很快……只有最終確定有用，真的沉澱下來，才推上去」→ 族群、各代候選、原始大輸出放 gitignore 的目錄或 scratchpad，只 commit 彙總與沉澱下來的節點。

- 思考設計輪時機（使用者 11-09 22:5x）：「思考設計輪不用限制說隔多久才跑，應該要用每完成一輪大的改進後就來看看。」→ 不按鐘點；每收完一條大改進線（或一輪施工）就開下一輪。
- LM Studio（使用者 22:5x）：「lm studio我就先關掉了，有需要的話litellm proxy的gpt低階模型如luna/terra就很好用了，也不會搶占到gpu。」→ 本地 LLM 需求改走 litellm luna／terra。

- 分工補充（使用者 22:5x）：「可以的話，實作，寫檔案等各種普通的，不太需要高階智能的文字處理，都交給codex gpt sol，或是litellm的sol」→ 實作與普通文字處理優先派 codex `-m gpt-6.1-sol -s workspace-write`（必帶 -m／-s）或 litellm sol；Claude 子 agent 留給設計、審查、驗收。

- LM Studio 又開了（使用者 23:1x）：「lm studio我還是開起來了，如果沒東西跑的話，可以拿他跑一些。」→ 可當閒置填充用；只用已載入的模型、不 load／unload。
## 現役線（頂層 ≤3）

| 線 | 模型 | 內容 | 狀態 | 產物 |
|---|---|---|---|---|
| N1 長跑 | （無 agent）| systemd `arcagi-n1-overnight`：sol-low·prims_py 鑄 296 題到 06:00，06:10 寫 overnight-summary；terra 比較 `arcagi-n1-cmp-terra` 跑完要補 compare.md terra 列 | 跑中 | reports/wax-night-1109/ |
| N2 長跑 | （無 agent）| systemd `arcagi-n2-overnight`：gpusearch 800 題深度 5→6→7，06:00 寫彙總 | 跑中 | reports/native-cuda-1109/overnight/（未 commit，晨報收） |
| GPU 補負載 | （主 session 開，無 agent）| systemd `arcagi-main-gpufill`：`native/bin/gpusearch-filler`（gpusearch 複本）跑 evaluation 主線未解 344 題深度 6 dedup 4，timeout 7h；功耗 60W→118W | 跑中（23:10） | reports/native-cuda-1109/filler/（未 commit） |
| N3 GPU 遺傳符號搜尋 | opus | 第 2 棒 N3b 23:3x PARTIAL（ce51644）：smoke 過、pop 524288 約 125W；長跑 `arcagi-n3-gp` 597 題到 06:00；比較 bench real 約 23:50、synth 約 00:30 結束，`arcagi-n3-fill` 自動填 report 表並留 bench/FILLED；**早期警訊**：GP 前 33 題標 solved 的 4 題 test 全錯（過擬合）。第 3 棒：00:37 排程派 opus 寫結論＋白話 | 長跑中 | reports/gpu-gp-1109/ |
| N4 題目特性採集（第 1 棒） | opus | 23:5x 停線 PARTIAL（3cdbb11 本機）：gpuprofile 規格 `gpuprofile-spec.md`、CPU 特徵工具 `native/tools/profile_features.py`（800 列 23 欄可跑）；GPU 剖面程式未寫；Makefile 片段待貼回；下一棒照 progress.md 5 步 | 停（待接手） | reports/task-features-1109/ |
| T2 思考設計輪 2 | opus 隊長 | 主題：樹⇄JSON 往返（整棵樹當個體）＋分層改進成本帳＋塊 B 雜訊尺與 Argon 守門；跑 01a→03＋施工第一塊 | 跑中（00:3x 派） | notes/rounds/gpu-night-1109/think-2/ |
| N4b GPU 剖面 | opus | 照 progress 5 步寫 gpuprofile、跑 800 題、features.csv | 跑中 | reports/task-features-1109/ |
| N5b seed 列舉 GPU 第一步 | opus | 照 seed-gpu-可行性「最小可驗一步」：大小 2–3 一階原語 GPU 生成＋求值＋指紋去重，跟 CPU Enumerator 同層比對＋吞吐比 | 跑中（23:5x 派） | reports/seed-gpu-1110/ |

## 待辦（有空位就派）

- **A1 自起 aos daemon＋aos agent**（使用者睡前授權「自己起aos daemon，自己開aos agent，自己改進自己的工作流」「權限自行設置」）：步驟照 aos 回信 `wf/inbox/done/20261109T2337-aos-DONE.md`（`.aos-run/` gitignore、unit `arcagi-aos-daemon`、先 curl litellm /v1/models 對模型名、agent 只給 read/ls、ws 指 arcagi）。先接用法 1：思考輪「讀檔挑毛病」段交 luna agent；看門狗只盯根 pid。已派（00:0x）。

- ~~題目特性採集~~（已派 N4）：把 N2／補負載的 gpusearch 輸出（及 N3 GP 的近似分數）整理成每題搜尋剖面資料檔（`wf-table/1`），給後續排序器／剪枝器／演化適應度用；若 gpusearch 目前不輸出近似資訊，改它多輸出（使用者 23:1x 建議 2）。
- **aos 樹上的分層改進／遺傳搜尋**（使用者建議 1～5，見 [總表/使用者方向](../總表/使用者方向.md)「11-09 夜建議」；aos 回信整理在 [aos-回信-樹演化](aos-回信-樹演化.md)，建議第一步＝樹⇄JSON 往返、共用子樹記引用）：T1 收輪後開思考輪 2 以此為主題。

## 早上待辦（使用者醒來後）

- 使用者 push（06:10 前備好清單）。
- aos mcp 接上＋wf 轉 aos 知識庫：等 aos 回信（23:21 REQUEST）準備設定；**今晚不重開 session**（使用者睡覺幫不了），早上由使用者重開。

## 等待中

- 使用者睡前會再給 ARC-AGI 建議 → 照錄進 [總表/使用者方向](../總表/使用者方向.md)，排進思考輪。

## 已收線

- A1 自起 aos 樹（23:5x）：`arcagi-aos-daemon.scope` 根 pid 177262（收：`kill -TERM 177262`）；t1＝luna 只讀（read/ls，拿掉範本的 4 個工具）問答 14 秒、2 呼叫、品質中等；寫入只落 `.aos-run/`；食譜 `aos-daemon/食譜.md`、kb `lead/aos_agent`；c209f0f。風險：scope 從子 agent 背景殼起，主 session 結束可能連帶倒——看門狗檢查表加一條。
- GPU 補負載 2（23:47）：功耗掉到 ~89W，主 session 加開 `arcagi-main-gpufill2`（gpusearch-filler2 跑 training 主線未解 253 題深度 6，到 06:00）→ 95W。
- N5 S1 forbid（00:0x）：加好、解集合完全一致（100 題三種預算），但只跳過 0.5～3% 候選、速度差在雜訊內——多數樣式產的值本來就被去重丟掉；真要省得靠大量挖掘樣式或 seed 列舉搬 GPU（可行性稿估 2～4×）。pytest 21 過（主 session 重跑核過）；d7c2ed6。
- K1 分層知識庫（23:3x）：`kb/` 23 節點（resume／lead／worker／project），memory 工具實測可讀、find 可搜，節點 ≤1.3KB；7f2ce39。交接書「先讀規矩」可改成「先 read kb `worker`／`lead`」。wf_kb 改指 kb/ 要改 ~/.cache/aos-mcp-arcagi/tools.json（夜跑寫入範圍外）→ 待使用者。
- T1 思考設計輪 1（00:2x）：04-總結簡報 寫好（7d16438）；計分卡 21 積木（幹活 4／休眠 5／休眠有動靜 5／未量 7）、曲線尺速度分數 43.5；待使用者看 Q1／Q5／Q4／A4；輪 2 主題＝樹⇄JSON 往返＋分層改進成本帳＋塊 B 雜訊尺與 Argon 兩警告守門。
- N1／N1b 蠟模比較（23:30）：選 sol-low·prims_py（全步 20.8%、每步 51.4%）；發現空樹 ≤4 節點連換色都擬合不到→先改語言；43d2764。

- N2 CUDA 雛形（22:55）：GPU 對 CPU 44.5×～105×、解集合一致、Python 399/399；1ca9a6f／78c7890。
- 看門狗（22:52）：c85bc42；`touch ~/arcagi-STOP` 全停、`scripts/arcagi_stop_all.sh` 連看門狗一起停。

## 晨報格式（aos 速查 A2、A3）

①一兩句結論（成了什麼、沒成什麼）②代定清單，每條附翻案處 ③要他裁的題 ≤5、每題附推薦。白話、一段一重點、術語用比喻帶過、不讓他查編號表；細節折疊、只講結論。睡著時不問，要裁的放「待你裁」附預設並照預設先做。

## 代定清單

（使用者起床時白話報告）

- kb 的 mcp 入口：沒改 tools.json（在寫入範圍外），`mcp__aos__wf_kb` 仍指 wf/。翻案：使用者把 AOS_MEMORY 改指 kb/（或加一個 kb 工具）後重開。
