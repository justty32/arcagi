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
| N4b GPU 剖面 | （無 agent，等長跑） | gpuprofile 寫好（55e907f），抽查 3c9b0459 rot180／00d62c1b fill_enclosed top-1=1.0，perfect 數與 gpusearch 一致；800 題剖面 `arcagi-n4-prof-{training,evaluation}` 跑中約 01:35 完，`arcagi-n4-finalize` 自動產 features.csv＋FINALIZED；01:47 排程派 N4c 收尾（README、白話、commit） | 長跑中 | reports/task-features-1109/ |
| N4c 特徵表收尾 | opus | **收線 02ff8fc**：800 題×62 欄 features.csv（239KB 入庫）、README 欄位說明、features-白話.md；抽查 3c9b0459 rot180=1.0、00d62c1b fill_enclosed>colormap=1.0。train 全對 70 題、≥0.9 有 316 題（208 題主線未解）；6 題 train 全對但主線沒解（2013d3e2、25d8a9c8、a79310a0、aabf363d、66e6c45b、be03b35f）→ 值得查 test | 收線 | reports/task-features-1109/ |
| N4d 六題查 test | opus | **收線 9f2f1c4**：3 題 test 也對（a79310a0、66e6c45b、be03b35f），3 題 train 湊對（2013d3e2、25d8a9c8、aabf363d）。漏解：a79310a0／66e6c45b 主線搜尋深度不夠（正解 4 步），be03b35f 被 r08 支持度門擋（D-r8-21 已接受）。GPU overnight phase-A 早搜到這 3 題正解但沒接進主線 → **待裁**：GPU 窮舉當 gated 候選來源（過 table/unseen 門＋同 test 輸出 ≥2 支程式支持），先在 training 量多出的假解 | 收線 | reports/task-features-1109/n4d-six.md |
| N4e GPU 候選收編量測 | opus | **收線 52ffd1e**：table/unseen 門對 GPU 程式全不擋（R1＝R0）；關鍵在接法：**補位**（主線放棄才用）training +2 對（46f33fce、a79310a0）＋1 假解（25d8a9c8）0 衝突；覆蓋接法 3 衝突淨 −1；R2（≥2 支同答）反擋正解。evaluation 審計 56→58（含 be03b35f 補回 D-r8-21 那 −1）。**待裁**：收，補位＋R1（預設，未動主線） | 收線 | reports/task-features-1109/n4e-gated.md |
| N4f GPU 補位接線 | opus→codex sol | **收線 2410beb**：環境變數 `ARCAGI_GPU_FALLBACK=<jsonl:...>`（照 ARCAGI_SYNTH 慣例）；關閉時 800 題輸出逐位元同改前；141 tests。training 開啟 147→149（+46f33fce、a79310a0，假解 +25d8a9c8，0 衝突），evaluation 審計 56→58。**待裁：要不要預設開**。違規備註：子 agent 專案內 rm 了自建未 commit 的 progress.md | 收線 | reports/gpu-fallback-1110/ |
| N4g 補位擴大來源 | opus | **收線 7812df3**：19 檔相容 GPU 輸出合併重放 → training 仍 149、evaluation 仍 58，一題沒多對，反多 3 假解（全來自 GP：8–9 步冗餘、寫死顏色）。N4f 進帳全來自 phase-A。建議：補位只接窮舉來源；接 GP 須加「不冗餘／長度≤6」與「寫死顏色」門（只在 training 定門檻）。06:00 後重放指令在報告第 3 節（晨報時跑） | 收線 | reports/gpu-fallback-1110/n4g-sources.md |
| T6 思考輪 6：GPU 候選來源路線 | opus | **收線 7aefcdd**：208 題「≥0.9 未解」中 161 題只比原樣高 ≤0.001（假訊號），真訊號 25 題；天花板再 0～3 題（training 0～1）。更正：主線放棄多為**預算型**（~12.5s 撞 max_nodes 2e6、停 d3：training 188／eval 293），提早停只 13／8 題。推薦 B（補位加不冗餘門）→A（d6 定向深搜）→C 無記表版；Argon 3 P0（B 規則參考了 eval 題等）已收。代定 H1–H12。待裁：此線值不值得續、FALLBACK 預設開否、准否對 search.cpp 提早停做 training 回歸 | 收線 | notes/rounds/gpu-night-1109/think-6/ |
| T7 思考輪 7：學習通道改進 | opus | **收線 3662d40**：學習只在 e0→e1 因 e1 後 gate 題固定 20 題、uses 排序不再變、judge 升 live 要「解新題」但增益來自「已解變快」（11 comb 只 1 升 live）；GA 中性因 uses/comb 都不在 genome。推薦 A：judge 與量尺對齊（變快也能升 live、逐 comb 記功），預期 +8～+25 bits 且 e2..e4 續漲。Argon P0 已收。**待裁 U1 准改 hammer（judge.py:42 等，新欄位預設關）、U2 停 GA 回圈（預設停）、U3 B_REF 不動**；下一步 T7-B 離線定門檻 | 收線（待裁） | notes/rounds/gpu-night-1109/think-7/ |
| N9 節點上限實驗 | opus | **BLOCKED a9762c8（前提更正）**：主線 max_nodes 是 2e7 從沒撞到；真正綁的是 `native/hybrid.py:9` 寫死 DEADLINE=19s（budget≈13–15s），T6 簡報那段引的是 arcbatch 預設。粗估 d3 停住的 148 題要走完 d4 中位需 ~90s | 收線 | reports/nodecap-1110/ |
| N9b hybrid 期限開關＋掃 | opus→codex sol | **收線** 0eaf09d、42123b5＋結果：188 題 d19→d120（6.6× 算力）只 +2 test 對（a3df8b1e、e3497940）、+3 假解、174 題仍逾時；d55 +1/+1。結論：加時間不划算，期限維持 19；開關留作實驗 | 收線 | reports/nodecap-1110/ |
| T4 思考設計輪 4 | opus（T4b 收第 2 棒） | 第 1 棒 d2a933d/41ffdc6；T4b：ec2f038（代定重議＋03）、20d95f6（meter/dumb，123 tests）、8e12893（報告）。主分數 gain_bits（減 epoch0、只 train）；原笨樹旋鈕 hammer 根本沒讀→改成停用副本的 growth/foundry/judge。實跑 20 題：(b) 原樹自比 Δ=0 過、(c) 3 種造假全 FAIL 過、**(a) 未過**：三棵斷學習樹 −90 bits 兩半同號但 z=−1.63（σ 55.3；學習只發生在 epoch0→1）。64 題全量重跑 fa06369：仍 FAIL z=−1.51（加題只加 σ）；no-learn 在 e0→e1 也漲 73 bits 來源不明。T4c：73 bits＝no-learn 沒關的學習通道（hammer 依 uses 排序算子，epoch.py:250/317），非量尺 bug；親代 173≈排序 85＋combs 88。預先登記新判準 f1991f8（對照 no-learn-all＝再清 uses；成對符號檢定 p≤.05、Δ≤−2、兩半同負）、程式 1629ce3（158 tests）；**t4c 重跑 PASS（02:05）**：親代 vs no-learn-all 18/18 題負、p=3.8e-6、Δ=−168.7 bits、兩半同負；null 0；造假/重算全過 → 量尺第一次能分出「會學 vs 不會學」。T4d：收尾 58e27ce（04-總結簡報；親代 168.7＝排序 70.1＋combs 98.6；T8 盲點：只改 comb 狀態的突變量不到）、§9 預先登記 7d987f9（5 子代雙尾符號檢定 Holm）；**g1 結果（02:14）：有效性全過，但 5 子代 c0–c4 每題 Δ=0**（gain 與 base 皆然）→ 演化在這把尺上零效果。T4e af886a2：c0 突變 hammer 不讀的節點 weight（GA bug）、c1/c2 comb 突變被 strip=all 剝掉（量尺盲點）、c3/c4 動到永遠選不到的 rt_sleep 路由列；g1 elites 是中性漂移 → 全零**不能**當 GA 沒用的證據。代定 T9–T12（預設：weight 移出標的、排除遮蔽列、round-trip 進代門檻、comb 子代 strip=targeted）。T4f：df225ec（§10 判準先登記）、7f95e5f（T9–T12，172 tests；新 effect.py 進代門檻；9 個突變標的永遠無效會被重抽）；新 g1（ws/evo/pop-t4f/）5 個不同子代全過 T11；G7 誤報（被別線 pytest-* 未追蹤夾觸發）。**g1′ 結果（02:44）：有效性全過，5 子代（3 targeted、2 all）仍每題 Δ=0** → 修好後的單步突變在 64 題 L=40000 上仍完全中性（2 題 fixture 上看得到變化、真題上看不到）。結論：現行 GA 單步突變太小；**待裁**：加大突變步幅（多步/組合突變）或停 GA 線、把資源移到量尺已證明有效的「學習通道」（uses 排序＋combs）本身的改進。不再翻案 | 收線（待裁） | notes/rounds/gpu-night-1109/think-4/、reports/think4-1110/ |
| N3e MDL λ 掃描 | （無 agent，長跑） | **收線 88aabd8**（05:45 SWEEPDONE）：λ 越大解越少、程式越短，但 on40 test 對恆 1 題（a79310a0）、假解比例 82–88% 不降；real-40 假解 100%。MDL 篩不掉假解，GP 不再調 λ | 收線 | reports/gpu-gp-1109/holdout.md |
| N5d B1 bank 常駐 | opus | **E8 不過→凍結 `--gpu-min 200000`**（9822723、19c9c59）。0 錯／0 差異、29 tests 過；上傳 sync 49.7→10.1s，但牆鐘 1e6 b1 56.4s vs gpu 54.2s vs cpu 10.2s：瓶頸換成每層同步一次（6230 層×~27ms，GPU 被夜跑佔滿在排隊）。要贏得「一次同步涵蓋多層／多題」。違規備註：實作 opus 自寫未交 codex；bench 開成 service 非 scope（arcagi-n5d-bench，1e7 補表中，跑完寫 DONE，補表 `python3 -I reports/seed-gpu-b1-1110/analyze.py <scratchpad>/n5d`） ；**1e7 補表**：cpu 125.9s／gpu 184.4／b1 172.9／b1hi 146.4，皆 0 差異；b1 16 次 fallback 未查 | 收線 | reports/seed-gpu-b1-1110/ |
| T5 思考輪 5：跨題合批／多層融合 GPU | opus | **收線 cf4c927**：合批上限 1.35×（補一階原語 1.6×）不值得；多層融合理論 5.7× 但須 lambda 上 GPU（1–3 月、受 E1/E5）。Argon 3 P0 已收。代定 G1–G15。待你裁：乾淨 GPU 窗口量 λ、MPS、E1/E5 鬆綁、准開 03；Argon 提 CPU 熱點（lambda 多範例一次評估、flat hash 去重）→ 開 N8 | 收線 | notes/rounds/gpu-night-1109/think-5/ |
| N8 CPU 熱點 | opus→codex sol | **收線 d657662、90901b4**：`native/bin/arcbatch-hot`（make -C native hot；native/src 未動）1e6/1e7 各 3 次 0/100 差異、31 tests。中位牆鐘 1e6 1.11×、1e7 **1.15×**（負載 9–15）。A lambda 呼叫快取命中 86% 但只 3–7%（雜訊內）；B 型別綁定/候選不逐個拷貝 +4～12%。下一步候選：整段 map/filter/fold 結果快取。**待裁：arcbatch-hot 換成預設** | 收線 | reports/cpu-hot-1110/ |
| N8b 下一個 CPU 熱點 | opus→codex sol | **收線** 64201ff、fdcb041＋補表：1e7 剖面高階函式 58%（迴圈 24.7、lambda 23.4、建清單 10.1）、一階評估 28.3。正式 bench（負載 14–19）：hot 1.137×、hot-c 1.111×、hot-d 1.149×（只比 hot +1.0%，<2% 不收），全 0 差異。快取／緩衝路線撈不到，下一步要動一階評估或迴圈結構 | 收線 | reports/cpu-hot-1110/n8b.md |
| N8c 一階評估熱點 | opus→codex sol | d1cfe67：選 H1（一階原語跨 train 範例逐原語緊迴圈，免每例重新 switch/store；seed_enum.cpp:856、seed_value.cpp:456），預估 4–8%。管線 arcagi-n8c-pipe（codex→build→tests→交錯 bench→analyze，05:35 截止）。違規備註：開成 .service 非 scope ；**收**：bench 首跑因 run_one 漏列 hot-e 失敗，主 session 補後重跑：1e7 hot-e 1.176×（對 hot +3.8%）、1e6 1.124×，0 差異、40 tests | 收線 | reports/cpu-hot-1110/n8c.md |
| N8d lambda 葉節點內聯 | opus→codex sol | **收線（不收）**：hot-f 對 hot-e 1e7 +0.3%、1e6 −0.7%，0 差異、43 tests；未過 2% 門。arcbatch-hot-e 仍最佳（本輪 1e7 1.212×）。CPU 熱點線到此告一段落 | 收線 | reports/cpu-hot-1110/n8d.md |

## 待辦（有空位就派）

- **A1 自起 aos daemon＋aos agent**（使用者睡前授權「自己起aos daemon，自己開aos agent，自己改進自己的工作流」「權限自行設置」）：步驟照 aos 回信 `wf/inbox/done/20261109T2337-aos-DONE.md`（`.aos-run/` gitignore、unit `arcagi-aos-daemon`、先 curl litellm /v1/models 對模型名、agent 只給 read/ls、ws 指 arcagi）。先接用法 1：思考輪「讀檔挑毛病」段交 luna agent；看門狗只盯根 pid。已派（23:4x）。

- ~~題目特性採集~~（已派 N4）：把 N2／補負載的 gpusearch 輸出（及 N3 GP 的近似分數）整理成每題搜尋剖面資料檔（`wf-table/1`），給後續排序器／剪枝器／演化適應度用；若 gpusearch 目前不輸出近似資訊，改它多輸出（使用者 23:1x 建議 2）。
- **aos 樹上的分層改進／遺傳搜尋**（使用者建議 1～5，見 [總表/使用者方向](../總表/使用者方向.md)「11-09 夜建議」；aos 回信整理在 [aos-回信-樹演化](aos-回信-樹演化.md)，建議第一步＝樹⇄JSON 往返、共用子樹記引用）：T1 收輪後開思考輪 2 以此為主題。

## 早上待辦（使用者醒來後）

- 使用者 push（06:10 前備好清單）。
- aos mcp 接上＋wf 轉 aos 知識庫：等 aos 回信（23:21 REQUEST）準備設定；**今晚不重開 session**（使用者睡覺幫不了），早上由使用者重開。

## 等待中

- 使用者睡前會再給 ARC-AGI 建議 → 照錄進 [總表/使用者方向](../總表/使用者方向.md)，排進思考輪。

## 已收線

- N7 R1 排序器探針（01:2x）：gpusynth 料學先驗＋代價分桶列舉（不丟候選），解集合 0 不一致；**E7 不過**：1e6 合併中位 140k→47.5k 但同題比值中位 1.00（只是 7 題換位）、1e7 1.07×、wall +84～95%（lambda 代價偏低，求值步數 4–5×）。白話：先驗反映合成器怎麼抽樣，不是 ARC 要什麼。下一步：量到解求值步數／wall、代價計入求值開銷、用題目不變量給代價（Argon 提案 4）、合成料要能產 lambda、用 400 題判。ec983be。
- T2 思考設計輪 2 收輪（01:0x）：04b 8484b44。管線成（樹⇄JSON、快撥＋雜訊尺＋守門、credit 帳、遺傳個體），但 C25 快撥 auc_L 全 20 → 未證演化有用。建議落地：1、6、7① 已；5 框架；2、3 半；4 雛形；7②、8 待下輪。待使用者看 5 條代定（D3/D17/D22 洩漏、D20、D25、D27、D6）。
- N6b gpusynth v2（00:5x）：語意對 seed_value.cpp 核 4.5 萬列 0 不一致（and/or 沒被生成、未實測）；28 原語、輸出指紋去重；30 s 相異率 3.7%→31.2%、每秒相異 4.5k→10.2k（10× 目標未達，2.3×）；約 1 分鐘後新相異樣本枯竭 → 要加原語或 lambda 才能再提。5 分鐘料 521MB 在 scratchpad（tmpfs，不 commit）。27bec54。`native/synth.jsonl`（40MB，N6 遺留）已加 gitignore。
- N3d GP holdout＋MDL（01:0x）：gpgp-ho 三旗標（預設不變）。MDL 把假 solved 砍半（on40：8→4、test 對 1 保留）；留一 holdout 反而更糟（失掉真解、留下的全錯）——ARC train 只 2–4 例、輸出常很小（1fad071e 留出例與另一例輸出相同），留一擋不住。下一步：MDL 設預設試 λ 0.006/0.01、輪轉 holdout 並跳過低資訊題、solved 須「簡化長度 ≤ 窮舉已證無解深度+1」、≥3 seed。9e8d90f、d5ef32d。
- N5c seed GPU 端到端（00:4x）：3 次中位：1e6 gpu 21.1 s vs cpu 9.1 s（慢 2.3×）、1e7 187.6 vs 129.4 s（慢 1.45×）；gpuhi 1e6 打平、1e7 慢 1.25×；解集合 0 列不同。瓶頸：Amdahl（可搬段僅佔 26% 時間）＋每層上傳 27 ms／launch 14 ms、子題重傳 bank。結論：只搬一階不值得再優化；下一步 lambda kernel 或 bank 常駐＋合批 launch（已併入思考輪 3 路線）。d6b738d、1ae1708。
- N6 M0 量基線（00:4x）：1e7 時 seed CPU 時間評估佔 83%（lambda 46%、一階 37%）、簿記 17%、if 0.1%、library 0 → E1 維持 B（排序器優先）、E5 lambda 門檻未達（46% <50%）；到解節點中位 1e6 140k（7 題解）、1e7 511k（10 題）；56% 片段 <256 節點 → 逐片段 GPU kernel 多是小批。gpusynth 雛形 1.4M 嘗試/s、留 111k/s 但只 4% 相異（多是 reverse/transpose/take/drop 變體）→ 瓶頸是多樣性不是速度；原語語意未對 seed_value.cpp 核。595dca5。
- T3 思考設計輪 3（00:5x）：2446264、d5a2b8f；只到設計。Argon 修了 fable 三個高嚴重：①排序器訓練料只有 7/100 → 改 GPU 隨機造程式產大量訓練料 ②「延後不丟」違反 seed 由下而上建 bank → 改代價分桶列舉 ③ lambda 本體不能查表 → map/zipwith 攤平成批次重用 20 個一階 kernel；`--gpu-min 200000` 等於全 CPU，改用 0 比。量基線＋學排序期間 GPU 造訓練料 → 與「能用 GPU 就用」衝突大致化解。03／施工待使用者早上核代定（預設：先做無風險的量基線 N6）。
- N3c GP 結論（00:3x）：合成題 GP 與窮舉 test 對題數相同（L5 16、L6 17、L7 12），GP 勝無選擇隨機基線（4.7× 快）但輸窮舉（6e7 vs 9e5 候選/s）；GP 沒挖到窮舉到不了的深度；真題過擬合：整夜前 232 題標 solved 7 題只 1 題 test 對。下一步：適應度加留一 train 例 holdout＋MDL 懲罰＋簡化；窮舉做淺層、GP 從前綴延伸。aab29f6、2dd4a12（N5c 交棒註；草稿在 scratchpad/n3c/n5c-draft.md，1e6 中位：cpu 9.1 s、gpu 21.1 s、gpuhi 9.1 s，解集合 0 不一致）。
- W1 工作流改進（00:3x）：TEMPLATE.handoff.md「先讀」改成先 read kb/worker 或 kb/lead；dispatch/README 加指標；新 kb/lead/handoff_lessons（開完長跑就交棒、用工具呼叫數 ≤40 估）；lint 無新壞連結（舊 30 條多在 think-1/01a）；7487779。
- N5b seed 列舉 GPU 第一步（23:5x）：20 個一階原語搬上 GPU，100 題第 2–6 層指紋集合與節點數 GPU==CPU 0 不一致；吞吐比 0.13×（L2）→2.6×（L3）→30×（L6）（只算生成＋求值＋雜湊段，上限值）；lambda 類仍在 CPU；pytest 22 過（主 session 核過）；3f73ec6。
- A1 自起 aos 樹（23:5x）：`arcagi-aos-daemon.scope` 根 pid 177262（收：`kill -TERM 177262`）；t1＝luna 只讀（read/ls，拿掉範本的 4 個工具）問答 14 秒、2 呼叫、品質中等；寫入只落 `.aos-run/`；食譜 `aos-daemon/食譜.md`、kb `lead/aos_agent`；c209f0f。風險：scope 從子 agent 背景殼起，主 session 結束可能連帶倒——看門狗檢查表加一條。
- GPU 補負載 2（23:47）：功耗掉到 ~89W，主 session 加開 `arcagi-main-gpufill2`（gpusearch-filler2 跑 training 主線未解 253 題深度 6，到 06:00）→ 95W。
- N5 S1 forbid（23:4x）：加好、解集合完全一致（100 題三種預算），但只跳過 0.5～3% 候選、速度差在雜訊內——多數樣式產的值本來就被去重丟掉；真要省得靠大量挖掘樣式或 seed 列舉搬 GPU（可行性稿估 2～4×）。pytest 21 過（主 session 重跑核過）；d7c2ed6。
- K1 分層知識庫（23:3x）：`kb/` 23 節點（resume／lead／worker／project），memory 工具實測可讀、find 可搜，節點 ≤1.3KB；7f2ce39。交接書「先讀規矩」可改成「先 read kb `worker`／`lead`」。wf_kb 改指 kb/ 要改 ~/.cache/aos-mcp-arcagi/tools.json（夜跑寫入範圍外）→ 待使用者。
- T1 思考設計輪 1（23:2x）：04-總結簡報 寫好（7d16438）；計分卡 21 積木（幹活 4／休眠 5／休眠有動靜 5／未量 7）、曲線尺速度分數 43.5；待使用者看 Q1／Q5／Q4／A4；輪 2 主題＝樹⇄JSON 往返＋分層改進成本帳＋塊 B 雜訊尺與 Argon 兩警告守門。
- N1／N1b 蠟模比較（23:30）：選 sol-low·prims_py（全步 20.8%、每步 51.4%）；發現空樹 ≤4 節點連換色都擬合不到→先改語言；43d2764。

- N2 CUDA 雛形（22:55）：GPU 對 CPU 44.5×～105×、解集合一致、Python 399/399；1ca9a6f／78c7890。
- 看門狗（22:52）：c85bc42；`touch ~/arcagi-STOP` 全停、`scripts/arcagi_stop_all.sh` 連看門狗一起停。

## 晨報格式（aos 速查 A2、A3）

①一兩句結論（成了什麼、沒成什麼）②代定清單，每條附翻案處 ③要他裁的題 ≤5、每題附推薦。白話、一段一重點、術語用比喻帶過、不讓他查編號表；細節折疊、只講結論。睡著時不問，要裁的放「待你裁」附預設並照預設先做。

## 代定清單

（使用者起床時白話報告）

- kb 的 mcp 入口：沒改 tools.json（在寫入範圍外），`mcp__aos__wf_kb` 仍指 wf/。翻案：使用者把 AOS_MEMORY 改指 kb/（或加一個 kb 工具）後重開。

> 04:2x 晨報草稿已預寫：`晨報-草稿.md`（5499e30）；06:04 cron 補 overnight-summary、N4g 06:00 重放、待 push 清單後定稿為 `晨報.md`。
