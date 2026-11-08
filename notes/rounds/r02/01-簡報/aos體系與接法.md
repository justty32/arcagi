← 入口 [01-簡報](../01-簡報.md)

## 6. aos 體系是什麼、能怎麼接（隊長讀過 proto8 docs、node-pool、kb-ideas 後整理）

**相關概念**（proto8/docs）：
- **資料夾＝程式**（C-68～C-70）：aos 只保證六個環境變數（`AOS_ENTRY`、`AOS_WS`、`AOS_STACK`…）和一支 `aos-exec [--ws WS] XXX [args]`；`XXX` 可以是檔、帶 `_entry` 的資料夾、或 `檔#/JSON指標`。被叫的程式有自己的 stack（預設 `$AOS_WS/.stack/`）。其餘全是慣例。
- 函數的 `_metainfo.json`（N-68）：說明、估的成本 `cost`（token／呼叫次數／時間）、逾時 `timeout_ms`；另有「他見的帳」`observed.jsonl`（實測用量）。不認得的 key 一律忽略（C-48）；**KISS 是最高原則**（C-56）；確定性（C-22）＝能寫死的節點換成程式，少走進 LLM。
- **本機已裝且實測可用**：`aos-exec`（隊長在 scratchpad 試過：資料夾＋`_entry` 腳本，stdin 傳得進、`AOS_WS`／`AOS_STACK` 有設）；另有 `aos-loop`、`aos-fsm`、`aos-daemon`、`aos-json`、`aos-llm`（問腦，要 llm-kernel daemon）、`aos-tools`、`aos-grow` 等。

**node-pool（想法 20，aos 使用者 11-08 已裁定的設計）**：
- 節點＝有 `_metainfo.json` 的定義資料夾；梯度＝投進節點 `_gradients.jsonl` 的一行信（誰、哪題、說什麼、分數）。
- 錢＝抽象分數（起步千 token＋秒/10，公式可改）。每批任務＝一個 epoch：頂層收「接受任務數×每任務價」，每層先報銷實際花費、利潤留 20%、80% 照**靜態引用次數**分給子節點；每節點每批扣房租；**連續 3 批 0 只列「建議退休」**，隊長按了才封存到 `defs.retired/`、可復活。檔：`pool/config.json`、`wallets.json`、`ledger.jsonl`（只追加）、`epochs/<n>.json`。
- **想法 21 壓縮**：規則被「同判決的更短規則」蓋住就標 `covered`、不刪（aos 試算 186→95 條有效、作答不變）；LLM 歸納本質每批 ≤1 次、≤2k token，只進 candidate。
- **想法 22 元優化**：改進「改進的過程」——aos 自己還在謝拉格語料上做，**不建議本輪碰**。

**對 arcagi 的對應**：積木（原語、學習器、巨集）＝節點；一次全量評測＝一個 epoch；「任務」＝一題，解出＝收入；被選中程式引用＝分紅依據；耗時＝花費；近失敗＝梯度信。

**接入選項**（可多選；隊長評估寫在後面）：

| 案 | 做什麼 | 成本 | 隊長評估 |
|---|---|---|---|
| **A1 積木資料夾化** | 每個積木一個資料夾 `blocks/<name>/`：`_metainfo.json`（說明、參數域、cost、kind=primitive／learner／macro、狀態 live／covered／retired）＋`_entry`（stdin JSON 網格→stdout 網格，可 `aos-exec` 單獨叫）。**搜尋仍 in-process**（逐步開程序會慢上千倍），registry 從資料夾樹讀 metainfo 對上 Python 實作；新積木（巨集）＝新資料夾、不改程式碼 | 中 | 最貼「資料夾＝程式」；巨集可以純資料（JSON 程式）不用寫 Python |
| **A2 求解器資料夾程式** | `aos/solver/_entry` 包 `arcagi` 求解一題；`arcagi eval --external "aos-exec … {input} {output} {trace}"` 跑一個小集合證明端到端 | 小 | 便宜的「真的接上」證據；全量用它會多開程序，只做小集合 |
| **A3 積木記帳（node-pool 簡化版）** | 每次全量評測＝epoch：解出題 × 價 → 依選中程式的積木引用分紅、扣房租（引用次數／耗時），寫 `pool/ledger.jsonl`、`wallets.json`；連續 3 epoch 0 → 建議退休（不自動刪）；近失敗寫進積木 `_gradients.jsonl` | 中 | 本輪只會有 1～2 個 epoch，退休不會真的觸發，但帳本骨架就位；可拿 r01 結果當 epoch 0 |
| **A4 壓縮／covered** | library learning 抽出的巨集若解題集被更短程式完全涵蓋 → 標 covered；live 積木同理 | 小（依附 S3） | 想法 21 的直接移植，跟 S3 綁 |
| A5 aos-llm 接 LLM 提案 | S5 經 `aos-llm` 而不是直接叫 API | 小～中 | 要 llm-kernel daemon 在跑，額度緊，可延後 |
| A6 元優化 | 改進「改進流程」 | 大 | 不建議本輪 |

