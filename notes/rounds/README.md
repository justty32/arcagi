# rounds — 照 aos 輪次試解 ARC-AGI-1（交棒總表）

冷啟動接手先讀本檔，再讀 [wf/SESSION-LOG](../../wf/SESSION-LOG.md) 與 `wf/inbox/` 頂層未辦的信。

## 現況（2026-11-08 12:55）

- 準備：資料已下載、pytest 全綠、identity 基線 0/400（`reports/baseline-identity/`）；題庫盤點 `docs/inventory/training.html`＋`training-features.csv`（commit 4af1160）。
- 量具完成（commit 677b966）：`arcagi eval --external`、`--traces`、`arcagi compare`，見 docs/solvers.md、docs/traces.md。準備完成 PROGRESS 已寄、論壇 p-20261108-113206-aed9。
- **第一輪已收輪**（2026-11-08）：evaluation **21/400**、training 57/400（identity 0、template 0／6）。產物 [r01/](r01/04-總結簡報.md)：01 簡報 → 02 fable 規劃 → 03 設計 → 04 總結簡報＋[代定清單](r01/代定清單.md)；程式 `src/arcagi/dsl/`＋`src/arcagi/solvers/search.py`；跑分 `reports/dsl-search-r01/`。
- **第二輪已收輪**（2026-11-08）：evaluation **28/400**、training **79/400**（r01 21／57，退步 0）。產物 [r02/](r02/04-總結簡報.md)：01 簡報（含 §9 使用者 12:05 新想法「優化產生積木」）→ 02 fable 規劃＋02b 增補 → 03 設計 → 04 總結＋[代定清單](r02/代定清單.md)；aos 接入在 repo 根 `aos/`（積木資料夾、求解器資料夾程式、node-pool 帳 epoch 0～2、謂詞產生器）；跑分 `reports/dsl-search-r02/`。
- **第三輪已收輪**（2026-11-08）：evaluation **32/400**、training **86/400**（r02 28／79，退步 0）。產物 [r03/](r03/04-總結簡報.md)：01 簡報 → 02 fable 規劃 → 03 設計 → 04 總結＋[代定清單](r03/代定清單.md)；公式型／抽取型積木產生器（`blocks/gen_formula.py`、`gen_extract.py`，落地 `aos/blocks/formula_*`、`extract_*`）、題目背景、投票、帳 epoch 3；跑分 `reports/dsl-search-r03/`。
- **第四輪進行中**（2026-11-08）：[01 簡報](r04/01-簡報.md)、[02 fable 規劃](r04/02-規劃-fable.md)、[03 設計](r04/03-設計.md) 完成 → 三線施工中（A 每物件規則、B 公式＋預算＋拆 pool、C 搜尋預算＋並行評測）。
- 收輪義務：寄 PROGRESS 到 aos inbox（`/home/lorkhan/repo/simple_tools/aos/wf/inbox/`，用 `wf/tools/inbox_send.sh --reply-to /home/lorkhan/repo/arcagi/wf/inbox/ ...`）＋論壇發帖。

- **支線**（aos 人力加入後可並行的工作，路徑劃清）→ [支線.md](支線.md)。

## 使用者經 aos 轉達的前提（原文在 wf/inbox 的信，處理完在 wf/inbox/done/）

- 用 aos 體系（符號邏輯）解 ARC-AGI-1；LLM 只用來找規則、寫程式、蒸餾，最終解題靠確定的程式；**神經網路盡量不用**。可暴力吃 CPU、可寫 CUDA（RTX 5060 Ti 16GB，nvcc 在 /opt/cuda/bin）。
- 方向問題不停線：自己代定、記 `代定清單`，回報時列給使用者翻案。
- **只讀參考庫**：aos `~/repo/simple_tools/aos/proto8/`（docs/、thinking/2026-11/07/arknights-kb/ 輪次範本、kb-ideas/、thinking/2026-11/08/node-pool/）、`~/code/playground-ak/`、`~/repo/paper_readings/`、`~/repo/machine_learning/`（progsynth_cpp 等）。不寫、不跑 proto8/install.sh。
- 評分注意：re-arc 的 verifier 是 training 400 題的現成 DSL 解答 → training 分數有洩漏風險，**以 evaluation 為準**。

## 防當機限制（使用者外出）

- 同時子 agent ≤3；不開 codex。CPU 批次 `nice -n 19`、worker ≤12；單批記憶體 ≤16GB（`systemd-run --user --scope -p MemoryMax=16G` 或 `prlimit`）；顯存 ≤12GB；swap 只有 512MB。
- aos 寄信叫停就暫停批次與新開子 agent。

## 論壇（使用者手機看）

- 發帖 `/home/lorkhan/repo/simple_tools/aos/wf/tools/forum_post.sh arcagi '<標題>' <檔|-> --tag arcagi [--source <檔>]`；回帖 `--reply <id>`；精華／置頂 `.../forum_admin.sh feature|pin <id> --as arcagi`。
- 時機：開輪、fable 規劃定稿、每輪總結（加精華）、重要代定、卡住。ELI5、結論先、細節摺疊。
- 已發：p-20261108-112500-3b33（開工）、p-20261108-113306-a220（r01 開輪）、p-20261108-113529-042d（r01 規劃，精華）、p-20261108-114523-7780（r01 總結，精華）；r01 PROGRESS 已寄 aos（20261108T1145）；p-20261108-114831-133b（r02 開輪）、p-20261108-115110-5d4e（r02 規劃，精華）、p-20261108-122252-d66d（r02 總結，精華）；r02 PROGRESS 已寄 aos；p-20261108-122524-d037（r03 開輪）、p-20261108-122741-4a4b（r03 規劃，精華）、p-20261108-124706-58a8（r03 總結，精華）；r03 PROGRESS 已寄 aos（20261108T1247）。

## 額度

主 session 帳號 11-08 11:30 已用 81%（11-09 04:00 重置）；到上限由 aos 改用它的帳號開 agent 接續 → 每步做完更新本檔。
