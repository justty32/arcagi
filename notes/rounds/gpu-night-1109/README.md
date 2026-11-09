# gpu-night-1109 — 夜跑看板（compact 後先讀這裡）

← [交棒總表](../README.md)｜授權與安全邊界 [總表/規矩](../總表/規矩.md)「11-09 夜跑授權」｜原信 [00-REQUEST](00-REQUEST.md)

## 目標（使用者 11-09 22:5x）

到 11-10 06:20 使用者起床前不停。順序：① 系統安全 ② 推進 aos 體系改進（非解題率）③ 多用 CUDA/GPU 做符號運算（GPU 擬合、遺傳符號回歸、符號＋神經混合）④ 每完成一輪大的改進就跑一輪思考設計輪（不按鐘點）（gpt sol 蒐集 → opus 匯總 → fable 設計＋agy Argon 審 → opus 細化 → gpt sol 實作）。

## compact 後檢查表（每次都做）

1. `systemctl --user list-units 'arcagi-*' --plain --no-legend`：`arcagi-watchdog` 必須 active；掉了就照 scripts/watchdog_night.sh 開頭註解重開（`systemd-run --user --unit=arcagi-watchdog --nice=10 /home/lorkhan/repo/arcagi/scripts/watchdog_night.sh`）。
2. `ls ~/arcagi-STOP`：存在＝使用者喊停，全停、不派新線。
3. `ls wf/inbox/`：頂層有信先辦，辦完 `git mv` 進 done/（注意未追蹤檔用 `mv` 再 `git add`）。
4. inbox 監看 Monitor（每 15 秒 `find wf/inbox -maxdepth 1 -name '*.md'`，30 分鐘到期要續）——compact 後若沒在跑就重開。
5. CronList 看 06:04 晨報排程在不在；不在就 CronCreate `4 6 10 11 *` one-shot（內容：核各線 overnight-summary、寫 晨報.md、寄 aos DONE）。
6. 下表「現役線」逐條確認狀態；子 agent 完成通知來了就照 dispatch 收線（對證據）並更新本表。
7. 每次 commit 後更新本表與 SESSION-LOG 再 push。
8. **GPU 不准閒**（使用者：「不要讓gpu閒下來，一整個晚上我都要靠它取暖」）：`nvidia-smi --query-gpu=utilization.gpu,power.draw,temperature.gpu --format=csv`；功耗長時間 <100W 或 util 掉下來就加 GPU 負載（開新的 GPU 搜尋長跑或加大 batch），溫度 ≤85°C。
9. aos 頂層熟使用者過去習慣：拿不準的流程、偏好、過去 thinking 就寄 REQUEST 問它（`wf/tools/inbox_send.sh --reply-to ... aos inbox ... REQUEST`），不自己猜。

## 子 agent context 管理（使用者 22:5x「子agent的context也要做管理」）

- 一條線＝一個里程碑；交接書寫死**交棒點**，到點就寫進度檔（`<產物夾>/progress.md`：做到哪、數字、下一步、關鍵路徑）並回報 `DONE`／`PARTIAL`，由主 agent 開新線接力，交接書只帶上一段產物路徑、不帶對話。
- 子 agent 讀大檔、掃大量報告、跑長輸出一律派孫 agent 或用 grep／head，只把結論帶回；長跑交 systemd 背景，不在 context 裡等。
- **30% 換手**（使用者 22:5x）：「子agent的context也要管理，當他們到30%的時候就要讓他們寫交接，換手了」→ 子孫 agent 估計 context 用到約 30%（粗估：累積讀進／產出約 60k tokens，或工具呼叫約 40 次）就停手寫交接（`progress.md`：做到哪、數字、下一步、關鍵路徑、在跑的背景單元），回報 `PARTIAL`；上一層開新 agent 從 progress.md 接手。交接書都要寫明這條並原樣下傳。
- 孫 agent 同樣適用；回報只給結論＋路徑，不貼原始輸出。

## 分工

- 思考設計輪時機（使用者 11-09 22:5x）：「思考設計輪不用限制說隔多久才跑，應該要用每完成一輪大的改進後就來看看。」→ 不按鐘點；每收完一條大改進線（或一輪施工）就開下一輪。
- LM Studio（使用者 22:5x）：「lm studio我就先關掉了，有需要的話litellm proxy的gpt低階模型如luna/terra就很好用了，也不會搶占到gpu。」→ 本地 LLM 需求改走 litellm luna／terra。

- 分工補充（使用者 22:5x）：「可以的話，實作，寫檔案等各種普通的，不太需要高階智能的文字處理，都交給codex gpt sol，或是litellm的sol」→ 實作與普通文字處理優先派 codex `-m gpt-6.1-sol -s workspace-write`（必帶 -m／-s）或 litellm sol；Claude 子 agent 留給設計、審查、驗收。

## 現役線（頂層 ≤3）

| 線 | 模型 | 內容 | 狀態 | 產物 |
|---|---|---|---|---|
| N1 蠟模 | opus | 提示法比較（litellm sol/luna/terra；gemma 中途關閉）→ 長跑到 06:10；第 1 棒 23:1x PARTIAL（c835198；sol-low prims_py 中途每步 50%、全步 23.8%），第 2 棒 N1b 接手 | 跑中 | reports/wax-night-1109/、notes/rounds/gpu-night-1109/wax-白話.md |
| N2 長跑 | （無 agent）| systemd `arcagi-n2-overnight`：gpusearch 800 題深度 5→6→7，06:00 寫彙總 | 跑中 | reports/native-cuda-1109/overnight/（未 commit，晨報收） |
| N3 GPU 遺傳符號搜尋 | opus | 以 N2 評估器為底做 GPU GP；第 1 棒 23:05 PARTIAL（06788bc，codex 寫碼中），第 2 棒 N3b 從 progress.md 接手 | 跑中 | reports/gpu-gp-1109/ |
| T1 思考設計輪 1 | opus 隊長 | sol 蒐集→opus 簡報→fable→Argon→opus 設計→sol 施工→收輪；流程與指令見 [思考輪-流程](思考輪-流程.md) | 跑中（22:5x 派） | notes/rounds/gpu-night-1109/think-1/ |

## 等待中

- 使用者睡前會再給 ARC-AGI 建議 → 照錄進 [總表/使用者方向](../總表/使用者方向.md)，排進思考輪。

## 已收線

- N2 CUDA 雛形（22:55）：GPU 對 CPU 44.5×～105×、解集合一致、Python 399/399；1ca9a6f／78c7890。
- 看門狗（22:52）：c85bc42；`touch ~/arcagi-STOP` 全停、`scripts/arcagi_stop_all.sh` 連看門狗一起停。

## 代定清單

（使用者起床時白話報告）
