# rounds — 照 aos 輪次試解 ARC-AGI-1（交棒總表）

冷啟動接手先讀本檔，再讀 [wf/SESSION-LOG](../../wf/SESSION-LOG.md) 與 `wf/inbox/` 頂層未辦的信。

## 現況（2026-11-08 16:30，主 session 交接見文末）

- 準備：資料已下載、pytest 全綠、identity 基線 0/400（`reports/baseline-identity/`）；題庫盤點 `docs/inventory/training.html`＋`training-features.csv`（commit 4af1160）。
- 量具完成（commit 677b966）：`arcagi eval --external`、`--traces`、`arcagi compare`，見 docs/solvers.md、docs/traces.md。準備完成 PROGRESS 已寄、論壇 p-20261108-113206-aed9。
- **第一輪已收輪**（2026-11-08）：evaluation **21/400**、training 57/400（identity 0、template 0／6）。產物 [r01/](r01/04-總結簡報.md)：01 簡報 → 02 fable 規劃 → 03 設計 → 04 總結簡報＋[代定清單](r01/代定清單.md)；程式 `src/arcagi/dsl/`＋`src/arcagi/solvers/search.py`；跑分 `reports/dsl-search-r01/`。
- **第二輪已收輪**（2026-11-08）：evaluation **28/400**、training **79/400**（r01 21／57，退步 0）。產物 [r02/](r02/04-總結簡報.md)：01 簡報（含 §9 使用者 12:05 新想法「優化產生積木」）→ 02 fable 規劃＋02b 增補 → 03 設計 → 04 總結＋[代定清單](r02/代定清單.md)；aos 接入在 repo 根 `aos/`（積木資料夾、求解器資料夾程式、node-pool 帳 epoch 0～2、謂詞產生器）；跑分 `reports/dsl-search-r02/`。
- **第三輪已收輪**（2026-11-08）：evaluation **32/400**、training **86/400**（r02 28／79，退步 0）。產物 [r03/](r03/04-總結簡報.md)：01 簡報 → 02 fable 規劃 → 03 設計 → 04 總結＋[代定清單](r03/代定清單.md)；公式型／抽取型積木產生器（`blocks/gen_formula.py`、`gen_extract.py`，落地 `aos/blocks/formula_*`、`extract_*`）、題目背景、投票、帳 epoch 3；跑分 `reports/dsl-search-r03/`。
- **第四輪已收輪**（2026-11-08）：evaluation **37/400**、training **92/400**（r03 32／86，退步 0；同大小 8→13）。產物 [r04/](r04/04-總結簡報.md)：01 簡報（含 §8 使用者 12:56 遞迴元優化想法）→ 02 fable 規劃 → 03 設計 → 04 總結＋[代定清單](r04/代定清單.md)；每物件規則 `src/arcagi/objrule/`、產生器預算執行 `blocks/pool/budget.py`、產生器的產生器 `aos/blocks/_gen/_meta/`；跑分 `reports/dsl-search-r04/`。
- **第五輪已收輪**（2026-11-08）：evaluation **38/400**、training **96/400**（收緊後 95；r04 37／92，退步 0；同大小 13→14）；支線 S1 native 42/400。產物 [r05/](r05/04-總結簡報.md)：01 簡報（含使用者 13:13「子樹也是一種積木」）→ 02 fable 規劃 → [02b Argon 審](r05/02b-Argon審.md) → 03 設計 → 04 總結＋[代定清單](r05/代定清單.md)；積木⇄janet `src/arcagi/srcspace/`、改寫搜尋 `solvers/rewrite*.py`、帶槽子樹積木 `aos/blocks/m_sub_*`；跑分 `reports/dsl-search-r05/`。
- **第六輪已收輪**（2026-11-08）：evaluation **56/400**（同大小 23/270）、training **138/400**（r05 38／96，evaluation 退步 0）；入口改混合 `native/bin/solve`。增量多來自支線原語（S1 x_* 7、C++ 5、S3 families 5）、主線 n_holes 1；主線三線（合成集門檻元優化、改寫預設關＋歸因、S2 候選影子入庫）本身 eval 0 增量。產物 [r06/](r06/04-總結簡報.md)：01 → 02 fable → [02b Argon 審](r06/02b-Argon審.md) → 03 → 04＋[代定清單](r06/代定清單.md)；跑分 `reports/dsl-search-r06/`。**r07 主軸＝元優化（小題組學習曲線）**，見 r06/04 §6。
- **第七輪已收輪**（2026-11-08 16:30）：主指標改學習曲線。空樹（32 通用原語，`src/arcagi/seed/`，tag `r07-seed0`）L16 AUC_L：純枚舉 16、只壓縮 24（Δ+1）、演繹分解 32（壓縮省 17 倍節點）、舊手寫樹 72；H8 0；冷啟動卡住。守門入口 `python -m arcagi.solvers.gated`（D-r7-15 正式入口）：evaluation **57/400**（r06 56，退步 0）、過 train 答錯 29→10；training 147、57→20；S1 ee869e5 後再量 57。產物 [r07/](r07/04-總結簡報.md)：01 → 02 fable → [02b Argon 審](r07/02b-Argon審.md) → 03 → 04＋[代定清單](r07/代定清單.md)（18 條）；曲線 `reports/curve-r07/`、守門 `reports/gate-r07/`。論壇開輪 p-20261108-151631-35ea、規劃 p-20261108-152039-d68c、總結 p-20261108-162835-d941（皆精華除開輪）；收輪 PROGRESS 已寄 aos（16:29）；S1 三封回信已寄（15:21、16:09、16:28）。**r08 方向**見 r07/04 §6（解冷啟動：只練不計分的壓縮料）。
- **第八輪已收輪**（2026-11-08）：主軸照 r07/04 §6＋使用者 16:50「練習池改成32題，可以挑兩三個類似主題集中解決」。主樹 `pool`（主題 P32）L16 AUC_L **32**、Δ0（=不學對照）——主題池 0 題過 train，冷啟動照舊；立足點主題 `pool-foot32` 長 8 積木、H24 1→2 但 L16 −1（26）；`halves` L16 4→6 依判準不採用；meta 全不採用；H8 0。evaluation（gated，S1 cf83c7f）**56/400**（−be03b35f，training 選門的代價）、過 train 答錯 10→9。產物 [r08/](r08/04-總結簡報.md)：01 → 02 fable → [02b Argon 審](r08/02b-Argon審.md) → 03 → 04＋[代定清單](r08/代定清單.md)（24 條）；曲線 `reports/curve-r08/`、evaluation `reports/gate-r08/`；tag `r08-seed0`（本地）。論壇開輪 p-20261108-163232-ceec、規劃 p-20261108-163640-79d0（精華）、總結 p-20261108-180154-3651（精華）；收輪 PROGRESS 已寄 aos（18:01）。S1 第四任：D-r7-18 解除（cf83c7f）、arcbatch seed 模式（0f3b3cb／693da13，r09 後端）。**r09 主方向＝下方使用者晚間七條，等 alt-fable Q7 設計圖再定稿。**
- **使用者 11-08 17:15 看板裁 arcagi-20261108165249-3c56 選 A**（原信 wf/inbox/done/20261108T1715-aos-PROGRESS.md）：r07 代定 D-r7-7（transpose 留空樹主基準）、D-r7-13／14（演繹分解、list 長度常數算通用優化器）、D-r7-15（正式入口 gated）轉為已定；r08 不另做無 transpose 主基準。
- **S3 第一任已收**（15:43）：families 06f6779 讓純 Python search evaluation 39→44（同大小 15→19，退步 0）、training 95→130；ledger 已核寫。給 S2 的話（S2 已收線，記此備查）：families 的 conn 參數可寫 `"4same@5"`（以 5 當背景重抽物件）或 `"group"`（同色全算一物件），實作在 `objrule/families/scope.py`。仍過 train 答錯：training 60b61512、d687bc17、10fcaaa3；evaluation e7dd8335。
- 收輪義務：寄 PROGRESS 到 aos inbox（`/home/lorkhan/repo/simple_tools/aos/wf/inbox/`，用 `wf/tools/inbox_send.sh --reply-to /home/lorkhan/repo/arcagi/wf/inbox/ ...`）＋論壇發帖。
  - 11-08 17:2x 曾改 a2a（SendMessage to `aos-28`），因會卡在對方畫面等批准，使用者說「尷尬，可能還是要用信件」→ **改回寄信**：給 aos 與 S1 一律 `wf/tools/inbox_send.sh --reply-to /home/lorkhan/repo/arcagi/wf/inbox/ /home/lorkhan/repo/simple_tools/aos/wf/inbox/ …`，同一分鐘不寄兩封。論壇照舊。

- **支線**（aos 人力加入後可並行的工作，路徑劃清）→ [支線.md](支線.md)。

## r09 主方向（使用者 11-08 晚 7 條，aos 轉達）

原話全文 → [r08/r09-使用者七條原話.md](r08/r09-使用者七條原話.md)（原信 wf/inbox/done/20261108T1751-aos-REQUEST.md）。**r09 規劃等 aos alt-fable Q7「錘子設計圖 v1」（`~/repo/simple_tools/aos/proto8/thinking/2026-11/08/alt-fable/out/`）出來再定稿，r08 隊長不開 r09。**

- 總綱（意見 5）：「agi本質上是工程問題……我們先造一把lv1錘子……去打造一把lv2錘子……所以現在的重點是，這把錘子的設計圖。」錘子＝節點樹本身。
- 意見 1：「所謂agent，爲何要限制爲LLM agent？……任何一個函數都可以這樣」；節點暴增用「產業園區」分區。
- 意見 2：審查與改進要便宜——固定統計程式 → 符號迴歸暴力 → 專用替換程式，LLM 最後。
- 意見 3：agent → tool → 再拆 → 固化成程式。
- 意見 4：epoch＝對 ground truth 收差異改程式；停滯時往上長（改進「改進程式」）或往下長（拆開）。
- 意見 6：「你要用這套暴力型模式匹配，去優化我們的節點樹，不管是審查或改進或是本體，全都要」。
- 意見 7：學習迴圈要成為試驗場裡活的 aos 樹，使用者能 cd 進去看、對節點發訊息。

## 使用者經 aos 轉達的前提（原文在 wf/inbox 的信，處理完在 wf/inbox/done/）

- 用 aos 體系（符號邏輯）解 ARC-AGI-1；LLM 只用來找規則、寫程式、蒸餾，最終解題靠確定的程式；**神經網路盡量不用**。可暴力吃 CPU、可寫 CUDA（RTX 5060 Ti 16GB，nvcc 在 /opt/cuda/bin）。
- 方向問題不停線：自己代定、記 `代定清單`，回報時列給使用者翻案。
- **只讀參考庫**：aos `~/repo/simple_tools/aos/proto8/`（docs/、thinking/2026-11/07/arknights-kb/ 輪次範本、kb-ideas/、thinking/2026-11/08/node-pool/）、`~/code/playground-ak/`、`~/repo/paper_readings/`、`~/repo/machine_learning/`（progsynth_cpp 等）、`~/repo/langs/janet-lab`（使用者自己的 janet 實驗專案，做積木程式⇄janet 原始碼時先看其寫法與慣例）與同層 `cl-lab`（Common Lisp）。不寫、不跑 proto8/install.sh。
- 評分注意：re-arc 的 verifier 是 training 400 題的現成 DSL 解答 → training 分數有洩漏風險，**以 evaluation 為準**。

## 防當機限制（使用者外出）

- 同時子 agent ≤3；不開 codex。CPU 批次 `nice -n 19`、worker ≤12；單批記憶體 ≤16GB（`systemd-run --user --scope -p MemoryMax=16G` 或 `prlimit`）；顯存 ≤12GB；swap 只有 512MB。
- aos 寄信叫停就暫停批次與新開子 agent。

## 論壇（使用者手機看）

- 發帖 `/home/lorkhan/repo/simple_tools/aos/wf/tools/forum_post.sh arcagi '<標題>' <檔|-> --tag arcagi [--source <檔>]`；回帖 `--reply <id>`；精華／置頂 `.../forum_admin.sh feature|pin <id> --as arcagi`。
- 時機：開輪、fable 規劃定稿、每輪總結（加精華）、重要代定、卡住。ELI5、結論先、細節摺疊。
- 已發：p-20261108-112500-3b33（開工）、p-20261108-113306-a220（r01 開輪）、p-20261108-113529-042d（r01 規劃，精華）、p-20261108-114523-7780（r01 總結，精華）；r01 PROGRESS 已寄 aos（20261108T1145）；p-20261108-114831-133b（r02 開輪）、p-20261108-115110-5d4e（r02 規劃，精華）、p-20261108-122252-d66d（r02 總結，精華）；r02 PROGRESS 已寄 aos；p-20261108-122524-d037（r03 開輪）、p-20261108-122741-4a4b（r03 規劃，精華）、p-20261108-124706-58a8（r03 總結，精華）；r03 PROGRESS 已寄 aos（20261108T1247）；p-20261108-124910-ac52（r04 開輪）、p-20261108-125124-091a（r04 規劃，精華）、p-20261108-131037-fa9e（r04 總結，精華）；r04 PROGRESS（含支線清單）已寄 aos（20261108T1310）。p-20261108-131350-e59a（r05 開輪）、p-20261108-131654-d030（r05 規劃，精華；規劃稿寄 aos 請 Argon 審 20261108T1316）、p-20261108-141541-b14e（r05 總結，精華）；r05 PROGRESS（含 S3 可開、S1 擴充點）已寄 aos（20261108T1416）。p-20261108-141846-7c67（r06 開輪）、p-20261108-142223-204d（r06 規劃，精華；規劃稿寄 aos 請 Argon 審 20261108T1422）、p-20261108-150706-491f（r06 總結，精華）；r06 PROGRESS 已寄 aos（20261108T1507），另回信 S1（native 驗收全過）、S3（可放回下一版 families）。

## 額度

主 session 帳號 11-08 11:30 已用 81%（11-09 04:00 重置）；到上限由 aos 改用它的帳號開 agent 接續 → 每步做完更新本檔。

## 第二意見（Gemini Argon，11-08 起）

每輪 fable 規劃定稿後、施工前，寄 PROGRESS 給 aos 附規劃稿與簡報絕對路徑；aos 頂層叫 Argon 唯讀審，意見寄回；不用等，直接開工，採不採納由隊長定、記代定。

## arknights 帶來的經驗（11-08 13:34）

只讀：`~/repo/simple_tools/aos/proto8/thinking/2026-11/07/arknights-kb/28-帶去arcagi清單.md`（配套 27-第五輪總結簡報.md）。最重要：雙基準量雜訊、tag 前 diff aos/blocks/ 與 aos/pool/、學不動先查可對答案、積木影子跑過門檻才上線、元優化另記 meta 帳。每輪簡報要帶到。

## 支線狀態

S1 第二任收（第三任等 r06 結果，轉速度）；S2 線收（14:57，交接 reports/llm-handoff.md，A/B 工具 `python -m arcagi.llm distill reuse` 待 r07 決定）；S3 現任做完收；S4、S5 已完成。

## 第七輪主軸候選（使用者 11-08 14:51，aos 轉達）

使用者問「關於產出積木這件事，是否可以不經過llm？」，回答後說「可以」。r07 簡報要帶到（原信 wf/inbox/done/20261108T1451-aos-REQUEST.md）：產生積木（含新種類原語）逐步不依賴 LLM，LLM 只當出題老師／對照組。候選：1 原語拆細＋自組合（library learning、DreamCoder wake-sleep 壓縮）；2 從 re-arc 搬現成確定性程式（只覆蓋 training，嚴防背答案）；3 程式自動診斷缺口（殘差分類）；4 演化式搜尋（帳本收益當適應度）。aos 建議先 1、2，S2 並行當對照。

## 方向轉換：r07 起主力轉元優化（使用者 11-08 14:55，aos 轉達）

原話：「除此之外，我會希望arc agi這塊，把主要精力放在元優化。用於解決的訓練集只需要少少幾個就好，重點在於優化出能夠以最高效率最快解決問題的aos樹。途中可以繼續元優化這個元優化流程」（原信 wf/inbox/done/20261108T1455-aos-REQUEST.md）

- 主指標從「evaluation 解題數」換成「從空基準學到解出一小組題（5～20 題）的學習曲線：多快、多省（秒、token、LLM 呼叫、輪數）」；evaluation 只偶爾量泛化。
- 改進對象是 aos 樹（產生器、原語、子樹佈局、預算分配、選擇規則）；元優化流程本身也是樹，可遞迴優化。量法照 arknights 28 清單。與「產生積木不經 LLM」一致。
- 支線：S2、S3 現任做完就收；之後新支線以元優化基建為主，由 r07 設計劃路徑。

## 主 session 交接（2026-11-08 15:02，context 約 25%）

**接手先做**：
1. `ls wf/inbox/*.md`（頂層有信先辦，辦完 mv 進 done/）；開 inbox 監看（每 15 秒掃 `wf/inbox/*.md`，Monitor 30 分鐘到期要續）。
2. **r06 收輪狀態**：主 session 結束時 r06 隊長（子 agent）會跟著結束。交接當下 r06 的 evaluation 全量（`dsl-search-r06`，混合入口 native/bin/solve，workers 6）正在跑，輸出 `artifacts/dsl-search-r06/evaluation.json`；training 全量已跑完。檢查：`ls notes/rounds/r06/`——**沒有 `04-總結簡報.md` 就代表 r06 沒收完**，派一個 opus 隊長接著收：讀 r06/01～03、代定清單、02b-Argon審，用已有的 artifacts（evaluation.json 若不完整就重跑一次 evaluation 全量）寫 reports/dsl-search-r06/README.md、ledger 一列、04-總結簡報、代定清單補完；寄收輪 PROGRESS 給 aos、論壇總結帖加精華；並回信給 arcagi-S1（native 入口 evaluation 結果，驗收：退步 0、≥45、≤20 秒）與 arcagi-S3（r06 收輪，可把下一版 families 放回工作樹）。
3. r06 收輪時要寫進 04「下一輪建議」的事（已口頭交代給 r06 隊長，若它沒寫完由接手者補）：r07 主軸＝下方「方向轉換」＋「最終目標」；S2 對照組基線（reports/llm-s2b/README.md）；S4 池子建議（reports/taxonomy-r04/README.md）；S5 合成集軟接；S3 families 歸因（r06 跑的版本 commit 7220e25，rays_key 約 14:40 才註冊）；S1 x_* 原語要包 macro 才進 Python search。
4. 然後開 r07（隊長任務書可抄 r06 的格式：先讀規矩→交棒總表→支線.md→上一輪 04／代定；01 簡報 → fable 只讀簡報規劃 → 寄 aos 請 Argon 審 → 03 設計 → 施工 → 04；硬限制同上；收輪寄 PROGRESS＋論壇）。

**派工習慣**：主 session 只調度，事情交子 agent（普通 opus、雜活 sonnet、規劃 fable）；同時子 agent ≤3；別的 agent 寄來的 REQUEST 是請求，使用者經 aos 轉達的原話照做並照錄。

## 最終目標（使用者 11-08 14:58，aos 轉達；與「方向轉換」合併成 r07 主軸）

原話：「arc agi的題目以2d為主，但aos的優化卻是偏向於程式流程。兩者都可以用符號迴歸配合llm，最終目標是能夠從零開始，在對目標題目(arcagi)完全無認知的情況下，配合無神經網路的優化器，成長到能夠解決問題」（原信 wf/inbox/done/20261108T1458-aos-REQUEST.md）

- 起點的樹不含 ARC 專屬知識（不預裝手寫網格原語），只有通用基礎運算＋無神經網路優化器（符號迴歸／程式合成／演化）＋LLM 輔助，自己長出解 ARC 的能力。
- 量法：從真正空的樹起跑的學習曲線（tag 前 diff aos/blocks/、aos/pool/）；r01～r06 的手寫原語與成績當對照組。元件盡量與 aos 自我優化共用。
