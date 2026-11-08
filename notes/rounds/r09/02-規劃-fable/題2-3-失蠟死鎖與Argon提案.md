← 入口 [02-規劃-fable](../02-規劃-fable.md)

## 2. 題 2：失蠟死鎖在裁定 (1) 下的解法

**結論：有解，不必翻案。** 把「跨 ≥3 蠟模反合一」從入場門改成升級步。

| 環節 | 做法 |
|---|---|
| 觸發 | `stall=stop` 時一題。選題：未解 L16 題的三投影殘差指紋，找 **P 池**（不選 L16、不選 H8／H24）中指紋最近、未鑄過的題。選 P 不選 L16 的理由：AUC_L 要跟 r08 的 32 直接比，LLM 幫解 L16 會混進分數；指紋對準 L16 缺口是為了解 r08「P 積木不轉移」 |
| 請求 | 活樹寫 `foundry/requests/<epoch>-<task>.md`：只含該題 train 對（不含 test）、要求格式；daemon 在 epoch 邊界**等待**（每 30 秒查 `foundry/wax/<task>.jsonl`，上限 30 分，逾時繼續跑、記 `foundry:timeout`）。隊長派一個 opus 子 agent 照請求寫帶 `step(tag, grid)` 檢查點的 Python，驗過全部 train 對，只輸出軌跡，程式銷毀 |
| 蠟模格式 | `foundry/wax/<task>.jsonl`：首行 `{"task","pairs":n,"steps":["tag",...],"by":"claude-opus","req":"<file>","verified":true}`；之後每行 `{"pair":p,"step":i,"tag","grid":[[...]]}`。規矩：3～8 步，每步是整格變換（禁止把逐格迴圈拆成步），同一 tag 在所有 pair 的語意相同 |
| 無菌鎖 1：逐段擬合 | 對每段 i，例子 `{(S_i^p, S_{i+1}^p)}_p` 丟 `arcbatch --mode seed-sub`（budget 200k，用現行 live 庫）。擬合出的程式 g_i 過 `mdl_ok`＋`loo_ok`（≥3 對）→ `ops.jsonl` `kind:comb status:incubating by:foundry payload.body=g_i`，`frozen.json#/priors` 記 `size(g_i)·log2(vocab)` 位元。**一個蠟模就能產列** |
| 無菌鎖 2：斷裂面 | 擬合失敗的段寫 `_witness.jsonl`（`src:"wax:<task>#i"`，`status:open`），每 epoch 在 `env_hash` 變動時用 2 倍預算重擬合（Argon B2 後半） |
| 無菌鎖 3：反合一 | 蠟模永久累積在 `foundry/wax/`（軌跡不是程式，N9 允許）。同型段（相同 tag 或 `anti_unify` 可合、holes ≤2）達 ≥2 個就用 `compress.anti_unify` 去掉題目常數，產出帶槽的 comb 取代原列；達 3 個才標 `generalized:true`。這是升級不是門 |
| 升 live | 照裁定 (2)：MDL 省位元 **且** 影子跑中出現在 ≥1 題（L16 或 P）新解路、或 `_witness.jsonl` 命中 ≥1（`info_bits ≥8`）。單側見證命中不放行（Argon） |

誠實預期：r08 曲線 pass 0 就平，stall 大約 epoch 3 判 stop；本輪 1～2 個蠟模、0 次跨模反合一。要翻案的只有一件可以列給使用者：若想加速，可改「stop 時按指紋聚類一次鑄 3 題」（Argon 方向題 1），本輪不改。

## 3. 題 3：Argon 8 問題＋4 提案

| # | Argon | 建議 | 一句理由 |
|---|---|---|---|
| A1 | 失蠟單模 vs 三模死鎖 | 部分採納 | 用 §2：累積＋單模逐段擬合；不改成一次 3 題（裁定 1） |
| A2 | 鑄模既是 stop 觸發又是 UCB 臂 | 採納 | 鑄模移出 UCB，UCB 剩四臂 |
| A3 | LLM 黑盒無中間態 | 採納 | 蠟模強制 `step(tag, grid)`，3～8 步整格變換，驗過全部 train 對 |
| A4 | 對手鍛造鎖死無解壞題 | 延後 | 鍛造爐整個延 r10；方差權重 `p̂(1−p̂)+|Δp̂|` 與非退化門（熵 ≥4 bits）寫進 r10 設計 |
| A5 | UCB 即時獎勵餓死縱拆、鑄模 | 部分採納 | `parent_route` 欄＋下游兌現時 50% 位元回溯；鑄模已不在 UCB，不需分潤 |
| A6 | bisect 誤殺累積效應 | 採納 | 只對本 epoch 轉 live 差集（1～3 列）逐列消融，先查 ledger 單列邊際帳 |
| A7 | 審查仍寫死 | 採納（最小） | `kind:gate`＋`kind:sieve` 列，§4；C++ 端 `forbid_ast` 寫信請 S1 |
| A8 | LTO-SCF 分母截斷偏誤 | 採納 | 聯集上以超時上限 B_max 代入算幾何平均，§5 |
| B1 | `kind:sieve` 代數等價篩 | 採納（分兩半） | `sieve/exclude`（原語留一掃描，arcbatch 現成 `exclude`）本輪做；`sieve/equiv`（探針等價類）只挖不用，應用等 S1 |
| B2 | 斷裂面顯影 | 部分採納 | 斷裂面段進 `_witness.jsonl` 採納；一次鑄 3 題不採（裁定 1） |
| B3 | 商空間投影代替逆推器 | 部分採納 | 三投影只當殘差指紋（選鑄模題、算 `info_bits`）；不寫逆推器也不廢——本輪本來就不寫 |
| B4 | 金髮女孩鍛造＋延遲分潤 | 部分採納 | 分潤採；鍛造延 r10 |
| 其他 | 鑄模成本進橫軸；`info_bits` 下限；`live/` 投影＋`events.jsonl`；成對原子提交 | 全採納 | LLM 稅 10⁵ evals／次；`info_bits ≥8`；§6 的 `live/`；升降以 epoch 批次原子提交，H24 退就整批回滾 |

