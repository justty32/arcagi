第八輪規劃稿：逐條定案簡報 §6 的七題，給隊長直接切線用；規劃者 fable 寫。

← [01 簡報](01-簡報.md)｜下一步 [03-設計](03-設計.md)

## 1. 練習池 P

**取題**：training 376 題（扣 L16、H8）中所有格子 ≤15×15 的，約 243 題（實數由 `scripts/r08_taskset.py` 產生寫死、附 sha，同 r07 題組規則；尺寸上限是算力偏置，寫明）。大格題留 r09 等 C++。

**預算**：L16 每 pass 每題固定 100k（AUC_L 才能跟 r07 的 32 直接比）。P 迭代加深：pass 0 為 25k，每 pass ×2，上限 400k（25k→50k→100k→200k→400k×4）。Python 端 12 workers 估 pass 7 約 6～8 分，8 pass 合計 <40 分。

**進 G1 的門（防過擬合）**：P 解出的程式要同時過 ① 該題 test 輸入也對（training 有答案，只當濾網不計分）；② S5 合成 pair ≥12/24 對。兩關都過叫 `clean_P`，才交 G1，權重與 L16 解相同；每題只送最小的一支。沒過的只記 `near` 計數，不進庫。

**報表**：`curve.csv` 加欄 `solved_P, clean_P, budget_P, lib_from_P`；`solved_P`／`clean_P` 當連續量畫曲線，**不進 AUC_L**。

誠實預期：pass 0 解 P 約 10～20 題、pass 7 約 25～45 題，clean 過濾後約七成；學到的多是 `take／reverse／transpose／map sort` 組合，鄰接類仍長不出。

## 2. 表達力：做兩項，第三項延 r09

| 項 | 做法（全在 `seed/decomp.py`，作演繹拆法不入盲枚舉） | 通用判準 | 驗證題 |
|---|---|---|---|
| (a) 兩半各自求解 | 給 train 對 (x,y)，取 k=len(x)//2，驗 y 能切成 y₁++y₂ 且兩半分別可由 `take k x`／`drop k x` 經同一支子程式 g 得出（子搜尋預算 20k）；也試 `zipwith h (take k x) (drop k x)` | 只用 len／take／drop／append／zipwith；ragged list、空 list、負整數測試不報錯 | 496994bd（已知大小 8） |
| (b) 巢狀 lambda／體深 3 | `lam_depth` 旋鈕開 3，**只在拆法產生的子搜尋**內允許 lambda 體再含 lambda，盲枚舉維持體深 2 | 僅改枚舉深度，無新原語 | ce4f8723（大小 18，誠實預期：100k 內可能仍解不到，靶是「近解距離縮短」） |

(c) 二維位置 `(i,j)` 延 r09。名稱只用 `split／halves／nest／depth`，`scripts/r07_purity.sh` 加 r08 新檔後照跑、禁用字樣不放寬。兩項各算一次 meta 動作（§3）。

誠實預期：(a) 把 pass 0 L16 由 4 升到 5；(b) 0～1。

## 3. 元優化

**連續主數字**：`logcost_L = Σ_{pass} Σ_{題∈L16} log2(min(解出所需節點, 100k))`（未解記 100k＝16.6；越低越好，每題解快一倍就降 1）。AUC_L 仍是門檻數字，`logcost_L` 是旋鈕判準。

**CRN 5 seed**：seed 1～5 固定寫在 `data/r08/knobs.json`；同 seed 下 before／after 用相同 G4 隨機源、相同 P 題序。meta 實驗用 **4-pass 短曲線、P 預算封頂 100k**（10 條曲線一回合約 40 分），只有被接受的旋鈕才跑全 8-pass。判準：5 對中 ≥4 對 `logcost_L` 不變差、平均降幅 ≥ max(1.0, 2×配對標準誤)，且任一 seed 的 AUC_L 不退。

**層 2**：Thompson 的 reward 由 0/1 改為 `Δlogcost_L／配對標準誤`（截斷 ±3）；旋鈕加 `budget_mult`（P 倍率 1.5／2／3）與 `clean_rule`（test 對／合成過半／兩者）共 9 個。

**加拆法當 meta 動作**：A 線每加一個拆法先掛旗（`decomp_set` 旋鈕），B 線用同一 CRN 判準跑；ledger 追加一行 `kind=r08-agent, action=decomp:<name>, commit, before/after(logcost_L, AUC_L)×5, agent_min, accepted`。不過判準的拆法保留程式碼、旗子預設關。

## 4. S1 協調（寫信，不碰 `native/`）

規格寫到能讓 S1 不看 Python 就做：① 程式 JSON＝巢狀陣列 `["op", …]`、`"$in"`、`"$0"/"$1"`、`["lam", body]`，附 20 支 L16 實際解當範例；② 原語語意以 `seed/prims.py` 為準，A 線產 `tests/seed/golden_prims.json`（每原語 ≥20 組輸入輸出，含 ragged／負數／空），S1 的 C++ 必須全過；③ 命令介面 `arcbatch --lang seed --lib <blocks.json> --tasks <json> --budget N --out <jsonl>`，每題回 ≤3 支 `{task, program, nodes, train_ok}`，Python 用 `seed.interp` **逐支重驗**，不一致者作廢並在 curve.csv 記 `native_mismatch`。信裡附 D-r7-18（只用 training 重選支持度門）。

S1 來不及（第 5 天仍無可用 build）：Python 撐——P 預算上限降 200k、12 workers、`nice -n 19`、`MemoryMax=16G`，預期 pass 7 ≤8 分；曲線加 `backend` 欄，兩套後端的曲線不混比。

## 5. 本輪整體門檻（缺一不過）

1. purity 通過（含 r08 新檔）、`llm_calls` 全 0。
2. **AUC_L(主樹) ≥ 40**（>dec-g1 的 32；pass 0 5 題撐 8 pass 就是 40，所以同時要求 **Δ_L ≥ +1 且來源是學到的積木**，不是 agent 改碼）。
3. 練習池 `clean_P` pass 7 ≥ 20，且 ≥ pass 0 的 1.5 倍（證明迭代加深有效）。
4. 至少 1 個源自 P 的積木被 L16 解用到（`lib_from_P` 使用次數 >0）。
5. meta ≥5 回合、5 CRN、ledger 齊；拆法 (a)(b) 各有一行 `r08-agent`。
6. H8：**目標 ≥1，不設硬門檻**。誠實說，鄰接類沒積木前 H8 多半仍是 0；寫報告時 0 就寫 0。

evaluation：只在收輪、且 S1 有新 commit 時跑一次 `gated`（守 ≥57、退步 0），不進門檻。

## 6. 分線（按路徑切；2 條 opus＋1 條 sonnet 雜活）

| 線 | 可寫路徑 | 禁區 | 驗收（可觀察） |
|---|---|---|---|
| A 表達力（opus） | `src/arcagi/seed/`、`tests/seed/`、`scripts/r07_purity.sh`（只加路徑）、`notes/rounds/r08/05-S1介面規格.md` | `grow/`、`aos/`、支線路徑 | ① 拆法 (a)(b) 掛旗可開關；② `pytest tests/seed` 綠，ragged 測試含新拆法；③ 496994bd 在 100k 內解出；④ ce4f8723 近解距離（錯格數）比 r07 小；⑤ `golden_prims.json` 產出、purity 過 |
| B 練習池＋曲線＋meta（opus） | `src/arcagi/grow/`、`scripts/r08_*.py`、`data/r08/`、`reports/curve-r08/`、`aos/seedlib/`、`aos/meta/ledger.jsonl`（追加） | `seed/`（只呼叫）、`solvers/`、支線路徑 | ① 題組 sha 雙生相同；② 主樹 8-pass curve.csv 含新欄，雙跑 sha 相同；③ `clean_P` 曲線與過濾掉的題數報出；④ 5 CRN meta ≥5 回合，判準程式化；⑤ 報 AUC_L、Δ_L、logcost_L、solved_H |
| C 協調（sonnet） | `aos/inbox/`（寄信）、`reports/gate-r08/`、`artifacts/gated-r08/` | 一切程式碼 | ① S1 信寄出（附 A 的規格與 golden）、D-r7-18 轉達；② 收輪 gated evaluation 一次（若 S1 有新 commit），報 對／退步／答錯三數 |

依賴：B 不等 A——pass 0 先用現有 `seed` 跑 P；A 交旗子後 B 以 meta 動作驗收。介面在 03-設計定死：`seed.enumerate(lib, tasks, budget_nodes, decomp_set: frozenset[str], lam_depth: int)`。機器：B 的 P 批次用 `systemd-run --user --scope -p MemoryMax=16G nice -n 19`，開跑前 `pgrep -af "arcagi eval"`。

## 7. 延到 r09

二維位置拆法 (c)；G2 re-arc 片段搬運、G3 殘差診斷（仍缺「片段 vs 整支 verifier」判別工具）；守門剩餘 `stamp_key`／移動＋裁切／`colormap`，families 表接自由度檢查，合成 pair 顏色正規化；>15×15 的練習題（等 S1 C++）；L16 擴到 32；層 2 超過連續 reward 的部分。
