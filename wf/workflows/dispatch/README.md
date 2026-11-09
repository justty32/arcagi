# dispatch — 派子 agent、交接書、領地、收線（派工者用）

[WORKFLOWS](../../WORKFLOWS.md)｜[INDEX](../../INDEX.md)｜派哪級模型 [team-model](../team-model.md)

把一件工作切成幾條線交給子 agent 跑，派工者負責**仲裁與驗收**、不深潛實作。使用者常長時間外出，主 agent 照本檔把量壓給子 agent，自己留 context 做判斷與跟使用者／aos 溝通。

**何時用**：一件工作大到要同時開幾條線（例：幾個求解器想法各派一條跑分、文件整理分批）；要派給別資料夾的 agent 做。
**何時不用**：一兩個檔的小改（交接成本大過收益）；需求還沒定、要跟使用者來回確認方向；只是要問一件事或送一則情報 → [inbox](../inbox/README.md)。

## Done when

- 交接書寫好（同機子 agent 可以直接當 prompt，跨資料夾的存成檔寄出），「驗收」段**條數 ≥ 1 且每條可觀察**。
- 下方「現役」表有該線一列，「可寫範圍」非空；收線後移到「歷史」並附完成證據。

## 流程

<!-- wf-nav -->
1. **切線**：按**明確列舉的檔案／目錄**切，不按功能切。**同一時間一處只准一條線寫**——兩條線寫同一檔，先寫的會被蓋掉，git 不會擋。跑分線另外注意 CPU：同一時間只准一條線跑全量評測（見 [experiments](../experiments/README.md)）。
2. **登記領地**：在下方「現役」表加一列。線只能追加自己那一格；收線與歷史整理歸派工者。
3. **寫交接書**：照 [TEMPLATE.handoff.md](../TEMPLATE.handoff.md)；送出前對一次下一節六條與 [lessons](lessons.md)。
4. **啟動**：同機用 agent 工具的子 agent（Claude Code 的 Agent／SendMessage），模型照 [team-model](../team-model.md)；跨資料夾（例：aos）用 [inbox](../inbox/README.md) 寄 `REQUEST`。給整條線的目標與邊界，不逐步替它重算。
5. **監看**：子 agent 回報終局（`DONE`／`BLOCKED`／`NEEDS-USER`／`FAILED`）＝正常結束；session 消失＝崩潰；輸出停滯或卡在批准提示＝活著但卡住。**還有現役線時不能宣告收工。**
6. **收線**：① 逐條核寫死的驗收（**對證據，不對自我宣告**——數字自己重跑或讀輸出檔核）；② 核 commit 與 push 狀態；③ 背景程序清乾淨；④ 跨資料夾的交接書檔移 `done/`；⑤ 該線從「現役」移到「歷史」。

**權重**：派工者的指示 > 交接書 > 其他線的來訊（來訊是情報與請求，不是命令）。

## 六條最容易錯的

<!-- wf-nav -->
1. **我是派工者，不是實作者。** 自己深潛實作會吃掉主 context，後面沒餘裕判斷。
2. **按檔案範圍切線，不按功能切。** 兩條線碰同一檔會互相覆寫。
3. **驗收條數寫死。** 留「以及其他你認為必要的驗證」的開口，線會為了保險亂跑、燒光額度。寫「回報只要這 N 條」。
4. **禁區要明寫，沒寫就等於允許。** 至少決定：能不能動 `src/`／`tests/`／`data/`、能不能下載、能不能裝依賴、能不能 commit／push、能不能跑全量評測。
5. **範圍詞會被遞移展開。** 「相關的」只寫包含條件，線會沿依賴圖展開成遞移閉包；用**排除法**界定邊界，並寫**件數或時間上限**，觸發就停下來回報。
6. **數字要能重現。** 跑分線回報要附完整指令、commit、輸出檔路徑；沒有這三樣的分數不收。

## 兩層派線

大任務可以走「主 agent → 子 agent → 孫 agent」：子 agent 可以再派、模型自選（[team-model](../team-model.md)）。每層對自己派出去的線負責驗收；**資源協調集中在主 agent**——要跑全量評測、要碰共用檔的，先回報上一層。

## 派工者休眠前的自檢

1. 列出還活著的線，必須為空；不為空就不能宣告「全部收完」。
2. 交棒寫 [SESSION-LOG](../../SESSION-LOG.md) 一行：誰在跑、卡在哪、下一步、誰監看。

## 領地登記

### 現役

| 線 | 模型 | 可寫範圍 | 唯讀／禁區 | 上線時間 |
|----|------|---------|-----------|---------|
| N1 蠟模夜跑（gpu-night-1109）| opus | `src/arcagi/llm/wax/`、`tests/llm/wax/`、`reports/wax-night-1109/`、`notes/rounds/gpu-night-1109/wax*.md` | `~/code/playground-arc1/ws/hammer/` 唯讀；LM Studio 不 load/unload；`aos/blocks/`、`data/` 禁寫 | 2026-11-09 22:40 |

### 保留給主 agent，任何線都不得寫

| 範圍 | 理由 |
|------|------|
| `AGENTS.md`、`wf/` 的 hub 檔（`INDEX`／`WORKFLOWS`／`SESSION-LOG`／`WAIT_USER`）、[experiments ledger](../experiments/ledger.json) | 多條線同時動會打架，收線時由主 agent 統一更新 |
| `wf/inbox/` 收信與搬 `done/` | 單一收件 agent（見 [inbox](../inbox/README.md)）|
| 本表既有內容 | 線只能追加自己那一格 |

### 歷史（收線後移來，附完成證據）

| 線 | 完成證據 | 收線時間 |
|----|---------|---------|
| N2 CUDA 暴力搜尋雛形 | 1ca9a6f／78c7890；GPU 對 CPU 44.5×（≤3，200 題）、105×（≤4，12 題）；212 題解集合一致、Python 驗 399/399；tests/native 17 綠；長跑 arcagi-n2-overnight 到 06:00（輸出未 commit，晨報收）；forbid 未做（不相依） | 2026-11-09 22:55 |
| r08-A 表達力 | b67dc2a；purity ok、tests/seed 85 綠；+halves L16 pass 0 4→6、nest 無效；golden_prims 747 組＋05 規格 | 2026-11-08 17:05 |
| r08-B 練習池曲線＋meta | fcf3f1c／51fe268／424d0d0；pytest 564 綠；pool AUC_L 32（=noG1）、foot32 26（clean_P 10→15）、meta 5 回合＋2 動作全不採用 | 2026-11-08 18:10 |
| r07-A 起點樹 seed | purity ok（32 原語）、pytest 523 綠；L16 pass 0 2→4（fe9b759→35049ef→0349a1d→efdee5d） | 2026-11-08 16:15 |
| r07-B 學習循環 | 曲線 e181649：empty 16、empty-g1 24（Δ+1）、dec-g1 32（節點 120160→7053）、old 72；pytest 524 綠 | 2026-11-08 16:20 |
| r07-C 守門 | 3129cc4；training 離線擋錯 35／誤擋 0／淨 138；gated evaluation 全量 57/400、答錯 29→10 | 2026-11-08 15:35 |
| r04-A 每物件規則 | pytest 333 綠；training 同大小未解 73 題子集 0→5、已解 39 題退步 0；物件視角抽取 6 live／14 covered | 2026-11-08 13:10 |
| r04-B 公式＋預算＋拆 pool＋_gen/_meta | pytest 337 綠；`blocks/pool/` 每檔 ≤300 行；預算 extract 5000／formula 11993／pred 8007；公式 35 live；meta 試 6 設定、最佳去 sq/div | 2026-11-08 13:25 |
| r04-C 搜尋預算＋並行 | pytest 320 綠；`--workers`；evaluation baseline 32/400＝r03、退步 0、牆鐘 30 秒；out_of_budget 0/400（預算從未是瓶頸） | 2026-11-08 12:58 |
| r03-A 公式 | pytest 312 綠；training 輸出尺寸不同 100 題子集 32→35；24 live／60 covered 公式積木；`aos-exec … _gen/formula --dry-run` 可叫 | 2026-11-08 12:50 |
| r03-B 抽取 | pytest 312 綠；training 子集 65→67（B 貢獻 1）；44 live／40 covered 抽取積木 | 2026-11-08 12:48 |
| r03-C 背景投票帳 | pytest 313 綠；training 子集 46→48、退步 0；essential／巨集下傳／產生器成本／真退休／generator_budget 測試在 | 2026-11-08 12:50 |

> 三張表是活狀態；膨脹到難讀就照 [STRUCTURE](../../STRUCTURE.md) 拆成 `CLAIMS.md`，本檔只留流程。

## 交接

- 交接書骨架 → [TEMPLATE.handoff](../TEMPLATE.handoff.md)；踩過的坑 → [lessons](lessons.md)。
- 線回報與催件 → [inbox](../inbox/README.md)；卡在使用者 → [WAIT_USER](../../WAIT_USER.md)。
