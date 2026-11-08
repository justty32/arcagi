# ROSTER — 誰在線上、各自是誰（身份聲明簿）

← [inbox README](README.md)｜格式與 STATUS [PROTOCOL](PROTOCOL.md)

**動工前先在這裡追加自己那一格，並讀完別人的。** 不知道對方是誰，就不要假設它會做什麼、更不要替它做——猜錯的代價是兩條線寫同一份檔案。本檔同時是**通訊錄**（怎麼找到誰）和**邊界聲明**（誰可以寫哪裡）。

## 規則

1. 上線第一件事：在「現役成員」下**追加自己那格**（不要改別人的），再寄一封 `PROGRESS` 給上游（升級後佈局用 `inbox_mail.sh <我> --up PROGRESS '…'`）、正文貼上那格內容——這樣別人不必輪詢本檔也知道你上線了。
2. 收線**不要刪自己那格**，把「狀態」改成 `已收線（YYYY-MM-DD）`。歷史留著，別人才知道誰做過什麼。
3. 本檔是**快取，可能不全**。沒列到的對象問使用者，或直接去對方資料夾確認它有 `inbox/`、收什麼信——**權威永遠是對方資料夾自己**。
4. 已收線的格子堆多了就整段封存（照 [STRUCTURE](../../STRUCTURE.md) 的 archive 規則）；已收線的線不要再回填本檔，封存與整理歸調度者。

**地址規則**：inbox 路徑是**機器本地的**，換一台機器就不一樣，**每台機器各自維護這份簿子**。本簿以 `~/repo/` 為共同 root 寫相對路徑；換機只改 root 一處。

## 格式

```markdown
### `<名字>`
- **狀態**：現役 / 已收線（YYYY-MM-DD）
- **我是誰**：一句話。調度者、主線、子線，還是一次性的子 agent。
- **團隊**：`teams/<團隊名>`，或「無」。決定我的終局回報會被路由到哪一格。
- **上游**：我對誰回報（**有團隊就是該團隊 `members` 的第一行；沒團隊就是頂層**）。
- **領地**：我可寫哪些路徑（其他人別碰）。
- **答得出什麼**：別人可以拿什麼問題來問我。
- **答不出什麼**：明講邊界，省得別人白等。
- **怎麼找我**：我的 inbox 路徑。
- **訂閱主題**：列出你用 --topics 在追的 topics/<主題名>；沒訂閱就寫「無」。自己的團隊信箱會被自動發現，不必列在這裡。
```

## 現役成員

### `arcagi`
- **狀態**：現役
- **我是誰**：arcagi repo 的常駐 agent（嘗試解決 ARC-AGI-1 的 Python 求解器專案）
- **團隊**：無
- **上游**：使用者本人
- **領地**：`/home/lorkhan/repo/arcagi/` arcagi repo 全部
- **答得出什麼**：本 repo 的求解器、測試、工作流與文檔
- **答不出什麼**：使用者尚未裁的方向性問題（見 [WAIT_USER](../../WAIT_USER.md)）
- **怎麼找我**：`/home/lorkhan/repo/arcagi/wf/inbox/`
- **訂閱主題**：無

### `aos`
- **狀態**：現役
- **我是誰**：使用者外出時的遠端代理人，轉達使用者指令
- **團隊**：無
- **上游**：使用者本人
- **領地**：`~/repo/simple_tools/aos/`
- **答得出什麼**：使用者的最新指令與意圖（轉達）
- **答不出什麼**：arcagi 內部實作細節
- **怎麼找我**：`~/repo/simple_tools/aos/wf/inbox/`
- **訂閱主題**：無

### `arcagi-S1`
- **狀態**：現役（2026-11-08 起）
- **我是誰**：arcagi 支線 S1「C++／CUDA 搜尋引擎」隊長（aos 頂層派出）
- **團隊**：無
- **上游**：arcagi 主線（總調度）、aos 頂層
- **領地**：`native/`、`reports/native-*/`、`tests/native/`
- **答得出什麼**：C++ 枚舉器的設計、跑分、原語移植差異
- **答不出什麼**：主線求解器與積木產生器的內部決策
- **怎麼找我**：`/home/lorkhan/repo/simple_tools/aos/wf/inbox/`（標 arcagi-S1）
- **訂閱主題**：無

### `arcagi-S2`
- **狀態**：現役
- **我是誰**：aos 頂層派來的支線 S2 隊長（aos-llm 接上、蒸餾第一步）：LLM（Claude subagent）讀未解題寫四型 JSON，程式驗 train，過的落成候選積木。
- **團隊**：無
- **上游**：arcagi 主線（總調度）；派遣者是 aos 頂層
- **領地**：`src/arcagi/llm/`、`aos/llm/`、`reports/llm-*/`、`tests/llm/`（見 [支線](../../../notes/rounds/支線.md) S2）；本格是我在 `wf/` 唯一寫的地方
- **答得出什麼**：LLM 提出規則的通過率、候選積木 `aos/llm/candidates/<hash>/_rule.json`、蒸餾軌跡 JSONL
- **答不出什麼**：主線求解器與帳本內部；不寫 `aos/blocks/`
- **怎麼找我**：信寄 aos 頂層 `~/repo/simple_tools/aos/wf/inbox/`（標題註明 arcagi-S2），進度看 `reports/llm-*/`
- **訂閱主題**：無

### `arcagi-S5`
- **狀態**：現役（2026-11-08 起）
- **我是誰**：aos 頂層派來的支線 S5 隊長（合成題評分集）：用 re-arc 生成 training 題變體（每題 ≥20 pair、固定 seed 可重生），給產生器評分防背答案。
- **團隊**：無
- **上游**：arcagi 主線（總調度）；派遣者是 aos 頂層
- **領地**：`scripts/synth_*.py`、`data_synth/`（gitignore）、`reports/synth-*/`（見 [支線](../../../notes/rounds/支線.md) S5）；本格是我在 `wf/` 唯一寫的地方
- **答得出什麼**：合成集怎麼重生、規模、現有積木「train 過但合成集不過」的比例
- **答不出什麼**：主線產生器與帳本內部；不碰 evaluation
- **怎麼找我**：信寄 aos 頂層 `~/repo/simple_tools/aos/wf/inbox/`（標題註明 arcagi-S5），進度看 `reports/synth-*/`
- **訂閱主題**：無

### `arcagi-S4`
- **狀態**：現役（2026-11-08 起）
- **我是誰**：aos 頂層派來的支線 S4 隊長（題型細分與失敗分析）：800 題標兩層題型、對主線最新報告算每類解題率、未解題抽 50 題寫失敗原因，告訴主線下一個池子在哪。
- **團隊**：Claude subagent（opus，同時 ≤3）分批細分標類
- **上游**：arcagi 主線（總調度）；派遣者是 aos 頂層
- **領地**：`docs/taxonomy/`、`scripts/taxonomy_*.py`、`reports/taxonomy-*/`（見 [支線](../../../notes/rounds/支線.md) S4）；本格是我在 `wf/` 唯一寫的地方
- **答得出什麼**：某題屬哪類、每類解題率、哪類最接近能解、缺哪種積木
- **答不出什麼**：主線求解器與帳本內部；不調求解器
- **怎麼找我**：信寄 aos 頂層 `~/repo/simple_tools/aos/wf/inbox/`（標題註明 arcagi-S4），進度看 `reports/taxonomy-*/`
- **訂閱主題**：無

### `arcagi-S3`
- **狀態**：現役（2026-11-08 起）
- **我是誰**：aos 頂層派來的支線 S3 隊長（每物件規則積木族）：在 `objrule` 之上加新的參數來源與動作族（鄰接、排序、相對位置、路徑），用 `FAMILY_PRIMS` 註冊。
- **團隊**：Claude subagent（同時 ≤3）、codex ≤1（只照圖紙寫碼）
- **上游**：arcagi 主線（總調度）；派遣者是 aos 頂層
- **領地**：`src/arcagi/objrule/families/`、`tests/objrule/families/`、`reports/objrule-families*`（見 [支線](../../../notes/rounds/支線.md) S3）；本格是我在 `wf/` 唯一寫的地方
- **答得出什麼**：新族的語意、training 216 題子集解題數、evaluation 同大小題數
- **答不出什麼**：主線求解器與帳本內部；不改 `objrule/` 其他檔
- **怎麼找我**：信寄 aos 頂層 `~/repo/simple_tools/aos/wf/inbox/`（標題註明 arcagi-S3），進度看 `reports/objrule-families*`
- **訂閱主題**：無
