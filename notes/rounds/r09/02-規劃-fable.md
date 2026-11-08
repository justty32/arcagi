第九輪規劃稿：逐題回答簡報 §7 的 7 題，把錘子設計圖 v3 的施工步 0～8 裁成半天能收輪、三條線能直接照做的版本；規劃者 fable 寫。

← [交棒總表](../README.md)｜[01 簡報](01-簡報.md)｜[02b Argon 審](02b-Argon審.md)

## 0. 結論先講（ELI5）

- 本輪造的「lv1 錘子」＝一棵在 `~/code/playground-arc1/ws/hammer/` 跑的資料夾樹：本體（arcbatch 枚舉）、審查（G1 門、剪枝）、改進（反合一造詞、拆法、鑄模）全變成 `ops.jsonl` 裡的列，每列有 `incubating→live→dormant` 三態，由樹自己的判準升降，不由人升。
- v3 步 0、1、4（comb／decomp／gate／sieve 列）、5、6、7 做**最小可量版**；步 2 只做格式與殘差指紋；步 3 鍛造爐、步 8 園區快取**延後**（理由：本輪沒有消費者）。後端全換 arcbatch，一個 epoch 約 10～20 秒，8 epoch 的主曲線 3 分鐘內；省下的時間拿去把「審查被暴力搜」真做出來。
- 失蠟死鎖在裁定 (1) 下**有解**：蠟模跨 epoch 累積，而且單一蠟模「逐段擬合」出的段直接當 `comb` 候選進 `incubating`，不必等三個蠟模；三模反合一改成「去掉題目常數」的升級步，不是入場門。代價：r09 大概只會看到 1～2 個蠟模、0 次跨模反合一。
- H24 硬底線的實施：升 live 只在 epoch 邊界成批原子提交；下一 epoch 主跑 H24 若低於上一 epoch，整批回 `dormant`、記 `rollback`、重跑該 epoch，兩次的評估次數都計入橫軸。
- 方向對不對，先寫死四個標記（§9），本輪命中其中兩個就算方向對；AUC_L、H24 的升降照意見 8 只看趨勢。

## 1. 題 1：v3 步 0～8 的取捨

| 步 | 做法 | 本輪驗收（可量） | 預估 |
|---|---|---|---|
| 0 五檔＋frozen | **做滿**。格式見 §1.1；`frozen.json` 記 H24／H8 題號 sha、purity、兩段判準、層數 ≤3、`priors`；tag `r09-seed0` | `python -m arcagi.hammer.check` 五檔格式全過；`scripts/r07_purity.sh` 加掃 `src/arcagi/hammer/` 與 `priors` 過 | A 線 40 分 |
| 1 身體 | **最小版**。每節點一個資料夾＋`_metainfo.json`＋`inbox/`；`_entry` 是 Python 函數 `run(rows)->rows`，`python -m arcagi.hammer.exec <node> <in.jsonl >out.jsonl` 走 stdin／stdout JSONL；in-process 直接 import 同函數。**後端換 arcbatch**（`--mode seed`，decomp 走 C++ 七拆法；需要 `halves`／`nest` 的設定退回 Python `seed.enum.solve`，兩者 S1 已證 0 差異） | (a) 相容模式 `--tree dec-g1` 重跑 L16 逐題 `program／nodes／nodes_to_first` 與 r08 同，`curve_sha`＝`7aebb3c73f28`；(b) 任一節點 `exec` 單跑輸出與 in-process 逐位同；(c) 8 epoch 主曲線 wall ≤5 分 | A 線 2 小時 |
| 2 約束見證 | **只做格式＋殘差指紋**。`_witness.jsonl` 由現有拆法子目標（`native/tools/seed_record.py` 已會錄）與蠟模斷裂面寫入；每題算三投影指紋 `proj_shape／proj_palette／proj_fg_mask`（Argon B3）給 stall 挑鑄模題用。不寫逆推器、不做 `pipe` 子節點 | 預設設定 sha 不變；`_witness.jsonl` 每 epoch 行數與 `info_bits` 分布印出 | C 線 1 小時 |
| 3 鍛造爐 | **延後 r10**。消費者（`rewrite` 列、縱拆）本輪不做，產 1,000 題合成料沒人吃；合成同分布審計沿用 S5 `synth_ok` 欄 | — | — |
| 4 ops 引擎 | **最小版**：`comb`（睡眠造詞＝現有 `compress.update`，改寫成列）、`decomp`（`halves`／`nest` 以列形式進 `incubating`，由樹判升降）、`gate`（§4）、`sieve`（§4）、`route`；`rewrite` 只留格式；孵化三態、`env_hash`、TTL；蒸餾不做 | ≥1 條 `comb` 列由樹判升 live（含 `evidence.new_solves`）；`decomp:halves` 列照兩段判準自動定升降；孵化門用 r08 殘差預核印「現況能過幾條」 | A 線 1.5 小時 |
| 5 停滯＋路由 | **最小版**。`stall` 看近 3 epoch：餓死（gate 進料 0）、飽和（solved_L、H24、lib_bits 全不動）、stop（飽和且未解 L16 的最佳 `near` 不動）；UCB 四臂：`rt_sleep`（反合一 m×2）、`rt_vsplit`（decomp 影子）、`rt_pool`（P 預算上限×2）、`rt_gatescan`（審查掃描）。**鑄模移出 UCB**，只由 stop 觸發 | 回放 r08 `pool` 曲線→判餓死、`meta` 曲線→判飽和；8 epoch 內四臂各被選 ≥1 次；`parent_route` 分潤記進 ledger | B 線 1 小時 |
| 6 鑄模廠＋無菌鎖 | **做**，照 §2 | ≥1 個蠟模經鎖產 ≥1 條 `comb incubating`；`frozen.json#/priors` 位元帳印出；`solve/` `llm_calls` 仍 0；LLM 稅 10⁵ evals／次計入橫軸 | B 線 1.5 小時＋隊長派 1 次 opus 子 agent（≤20 分） |
| 7 評審 | **最小版**：ΔAUC_total 只報；LTO-SCF 用聯集截斷版（§5）；算子二分改「只對本 epoch 轉 live 差集逐列消融」（通常 1～3 列） | 兩數印出；ledger `layer:2` 列 ≥5（gate-scan 供應）；若 H24 退，消融找出 ≥1 列並標 `blamed_by` | A 線 45 分 |
| 8 收輪 | 園區快取**延後**（arcbatch 已秒級，無可量收益）；gated evaluation 量一次；Argon 審 | evaluation 數字與 r08 56 並列；OOM 0 | 隊長 1 小時 |
| 選配 守門搜尋 | 不做（裁定 4；sieve 已是同類 layer-2 證據） | — | — |

### 1.1 五檔欄位（施工線照抄）

| 檔 | 一列／一鍵 |
|---|---|
| `_metainfo.json`（每節點） | `{"name","kind":"solve\|gate\|grow\|stall\|route\|judge\|foundry","entry":"arcagi.hammer.body:run","reads":["ops.jsonl","truth/train"],"writes":["epochs/<n>/solutions.jsonl"],"status":"active\|paused","weight":1.0,"born":{"epoch":0,"by":"agent-r09"}}` |
| `_witness.jsonl` | `{"id","task","pair":null\|int,"dir":"fwd\|bwd","src":"decomp:map\|wax:<task>#<i>","examples":[[in,out],...],"props":{"shape":[r,c],"palette":[...]},"info_bits":float,"status":"open\|fitted\|dropped","fit":{"program","nodes"}\|null,"epoch"}`；`info_bits`＝非 null 格相對背景熵的縮減量，<8 不入庫（Argon） |
| `ops.jsonl` | `{"id","kind":"comb\|decomp\|rewrite\|route\|gate\|sieve","status":"incubating\|live\|dormant","payload":{...},"sig","mdl_bits","evidence":{"new_solves":[...],"witness_hits":0,"shadow_epochs":0},"ttl":3,"env_hash","parent_route","by":"sleep\|foundry\|agent-r08\|user\|gate-scan","born":{"epoch","by"},"blamed_by":null}`。`payload` 依 kind：comb `{"body"}`、decomp `{"name":"halves"}`、gate `{"params":{...}}`、sieve `{"exclude":[...]}` 或 `{"forbid_ast","canon"}`、route `{"arm","prior_w"}` |
| `ledger.jsonl` | `{"kind":"epoch\|promote\|rollback\|layer2\|say\|foundry\|stall","epoch","layer":1\|2,"by","op_ids":[...],"before":{"solved_L","solved_H24","logcost_L"},"after":{...},"judge":{"stage":1\|2,"accepted","mean_drop","se"},"evals":{"body","shadow","meta","foundry","llm_tax"},"time"}`；收輪時整檔附進 `aos/meta/ledger.jsonl`（`kind=r09`） |
| `frozen.json` | `{"schema":"hammer-frozen/1","h24_floor":"per-epoch no regress","holdout":{"H8":{"n":8,"sha"},"H24":{"n":24,"sha"}},"purity":{"script":"scripts/r07_purity.sh"},"judge":{"stage1":{"new_solves_min":1,"h24_regress":false},"stage2":{"not_worse_frac":0.8,"drop_min":1.0,"se_mult":2}},"layers_max":3,"priors":[{"id","bits","src":"wax:<task>","epoch"}],"budgets":{"L":100000,"P0":25000,"P_cap":400000,"epochs":8},"llm_tax_evals":100000}` |

`env_hash`＝`sha1(sorted live comb bodies ＋ live sieve exclude ＋ live gate params)` 前 12 碼；任何 `dormant` 列在 `env_hash` 變動時自動回 `incubating`、TTL 重設。

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

## 4. 題 4：審查被暴力搜的最小實作

兩種列，都由 B 線的 `scan` 動作用 CRN 短曲線暴力掃，都走同一兩段判準，都要 H24 不退：

| 列 | payload | 搜什麼 | 量法與門檻 | 成本 |
|---|---|---|---|---|
| `gate_g1`（起步一列 live） | `{"mdl_div":1.0,"loo_frac":0.25,"loo_min_pairs":3,"lib_cap":16,"retire_after":2,"m":3,"k":2.0,"max_holes":2}` | 單因子鄰域：`mdl_div∈{0.5,1,2}`、`loo_frac∈{0.1,0.25,0.5}`、`lib_cap∈{8,16,32}`、`retire_after∈{1,2,3}`、`k∈{1,2,4}`、`max_holes∈{1,2}`，約 12 個單因子變體＋8 個雙因子組合 | 每變體跑 3 CRN seed × 4 epoch 短曲線；兩段判準：先比新解題數（≥2/3 seed 多解且 H24 不退），題數同再比 logcost（≥80% seed 不變差、降幅 ≥max(1, 2SE)）；過者新列 `live`、舊列 `dormant`，ledger `layer:2 by:gate-scan` | 20 變體 × 3 seed × 4 epoch ≈ 240 短 epoch，arcbatch 每個 ≈2 秒 → **約 8 分** |
| `sieve/exclude` | `{"exclude":["<prim>"]}` | 32 原語逐一留一（arcbatch `configs.exclude`，重驗仍用全部原語） | L16＋P 解集**不變**（0 掉題）且 Σ`nodes_to_first` 降 ≥5% → 列進 `incubating`，影子 2 epoch 仍 0 掉題且 H24 不退才 `live`；`env_hash` 變動即回孵化重驗 | 32 × 1 pass ≈ 1 分 |
| `sieve/equiv`（只挖） | `{"forbid_ast","canon"}` | 5 張 4×4 隨機探針，size ≤3 程式用 `--mode seed-run` 算值，觀測等價分組 | 只印：等價類數、估計可剪分支比例；寫 S1 信請 C++ `configs.forbid` | 10 分 |

兩段判準本身與 H24 底線寫在 `frozen.json`，**本輪不被搜**（真值隔離：審判準的人不能是被審的）。這是意見 6 在 r09 的邊界，04 要寫明。

## 5. 題 5：主曲線與 H24 硬底線

| 項 | 定義 |
|---|---|
| 題組 | L16／H8／H24 **照舊**（`data/r08/taskset.json` 的 learn／holdout／holdout24，sha `418234a6…`）；P 改 `P48`＝foot32 ∪ 以三投影指紋對 12 題未解 L16 最近的 16 題（扣 L16／H8／H24，規則寫死在 `scripts/r09_taskset.py`，先寫規則再產生） |
| 主數字 | `AUC_L = Σ_{epoch 1..8} solved_L`（與 r08 的 32 直接比）；`solved_H24` 逐 epoch；`logcost_L` 照 D-r8-10 |
| 新增只報 | `ΔAUC_total`：橫軸 log₁₀(累計評估次數)＝本體＋影子＋meta（gate-scan、sieve 掃描）＋foundry（seed-sub 擬合節點＋LLM 稅 10⁵/次）；縱軸 H8＋H24 盲測解出數；減去同橫軸範圍、不學的 `dec-g1` 對照面積 |
| LTO-SCF∪ | P48 以 `sha1(task_id+"r09AB")` 對半切；A 折跑 8 epoch 提煉 live 列，凍結套到 B 折量 1 pass；在聯集 U＝Solved_base ∪ Solved_+A 上，未解題以 B_max＝100k 代入，幾何平均加速比；要求前提「不丟任何原已解題」；bootstrap 90% 下界一併印 |
| 每 epoch 流程 | ① 主跑（live 列）→ ② gate 節點（live `gate_g1` 參數）→ ③ grow（反合一造 `comb incubating`）→ ④ 影子跑（live＋incubating）→ ⑤ stall／route → ⑥ 判準：對每條 incubating 列查 `evidence`，達裁定 (2) 者列入本 epoch 升級批 → ⑦ 寫 `epochs/<n>/`、`live/_status.json`、`events.jsonl` |
| H24 底線 | 升級批在 epoch n 末原子提交，epoch n+1 主跑 H24 < epoch n → 整批回 `dormant`（`blamed_by:"h24@n+1"`）、庫回 `epochs/<n>/blocks.json`、ledger `rollback`、**重跑 epoch n+1 主跑**，重跑列標 `rolled_back:true`；兩次評估都計入橫軸。批 >1 列時逐列消融（≤3 次重跑）找出拖累列，只那一列留 dormant，其餘下 epoch 再試 |
| 震盪容許 | `incubating` 數、`lib_bits`、ΔAUC_total 可上下；AUC_L 不設單調要求（意見 8） |

## 6. 題 6：活樹最小形狀

```
~/code/playground-arc1/ws/hammer/
  README.md        怎麼看、怎麼跑、怎麼停（C 線寫）
  RUN              存在＝daemon 繼續；`ctl stop` 刪它，引擎在下個 epoch 邊界退出
  ctl              → uv run python -m arcagi.hammer.ctl（薄殼）
  _view.sh         印 live/_status.json、本 epoch 曲線列、未解題殘差色塊（ANSI）
  _metainfo.json frozen.json ops.jsonl ledger.jsonl        根五檔之四
  truth/train/taskset.json  truth/cal/ids.json（H8、H24 只放題號）
  nodes/{solve,gate,grow,stall,route,judge,foundry}/   每個：_metainfo.json、inbox/、outbox/、_witness.jsonl
  foundry/requests/{pending,done}/   foundry/wax/
  epochs/<n>/{curve.csv,solutions.jsonl,blocks.json,status.json}
  live/{_status.json,events.jsonl,daemon.pid}
```

| `ctl` 指令 | 行為 |
|---|---|
| `run --epochs N [--daemon]` | 建 `RUN`、寫 `daemon.pid`，跑 N 個 epoch；`--daemon` 用 `setsid nohup` 背景跑，log 到 `live/daemon.log` |
| `stop` | 刪 `RUN`；引擎每 epoch 邊界查一次，≤1 epoch（≤60 秒）內乾淨退出並寫 `events: stopped`。`stop --now` 另送 SIGTERM，引擎捕捉後完成當前寫檔再退 |
| `status` | 印 epoch、各節點狀態、pending 請求、incubating／live／dormant 數、最近 5 條 events |
| `say <node> "<文字>"` | 寫 `nodes/<node>/inbox/<ts>.json` `{"cmd":"say","text"}`；引擎下個 epoch 邊界讀，回 `outbox/<ts>.reply.md`、ledger `kind:say by:user` |
| `pause <node>` / `resume <node>` | inbox `{"cmd":"pause"}`；該節點 `status:paused`，引擎跳過它（solve 不可暫停，會回拒並說明） |
| `weight <route_id> <w>` | inbox 到 `route`：改該 `route` 列 `payload.prior_w`，UCB 下 epoch 生效，ledger 記前後值 |
| `add-op '<json>'` [`--live`] | inbox 到 `grow`：追加一列 `by:user status:incubating`（走同一判準升級）；`--live` 直接 live 但 `born.by:user`，lv 判準依 v2 規則不算樹自長 |
| `ops [--status live]`、`ledger --tail N`、`view [epoch]` | 查表 |

訊息處理規則：所有 inbox 只在 epoch 邊界被讀（引擎單執行緒，無鎖）；每封產生一條 ledger 與一個 reply 檔；格式錯的回 reply 說明、不中斷。沒有 daemon 時資料夾一樣可 `ls`、`_view.sh` 讀最後一個 `epochs/<n>/`。

## 7. 題 7：分工

| 線 | 模型 | 路徑 | 交付與驗收 | 時段 |
|---|---|---|---|---|
| A 核心引擎 | opus | `src/arcagi/hammer/{formats,check,node,exec,body,gate,grow,judge,epoch,ctl}.py`、`scripts/r09_hammer.py` | 步 0（先做，40 分後 B／C 開工）→ arcbatch 後端＋相容模式重現 `7aebb3c73f28` → epoch 流程＋影子跑＋H24 回滾＋comb／decomp 列 → ΔAUC_total、LTO-SCF∪、差集消融 | 0:00–3:00 |
| B 審查暴力搜＋鑄模 | opus | `src/arcagi/hammer/{scan,sieve,stall,route,foundry}.py` | gate-scan（ledger `layer:2` ≥5）；sieve/exclude 掃描；stall 三判與回放 r08 驗收；UCB 四臂；蠟模解析→seed-sub 逐段擬合→comb 列；寫 S1 信（`forbid`） | 0:40–3:00 |
| C 活樹雜活 | sonnet | `~/code/playground-arc1/ws/hammer/` 骨架與 README、`_view.sh`、`ctl say/pause/weight/add-op` 殼、`live/` 投影與 `events.jsonl`、`scripts/r09_taskset.py`（P48）、`scripts/r09_report.py`、purity 腳本加路徑、三投影指紋 | 使用者可 `cd`＋`ls`＋`_view.sh`；`ctl stop` 在 ≤1 epoch 停；三種訊息各產一條 ledger＋reply；P48 規則先寫後產、附 sha | 0:40–3:00 |
| 隊長 | — | — | 3:00 整合跑主曲線；stop 時派 1 個 opus 子 agent 鑄模（≤20 分、≤2 並行）；4:00 評審數字、gated evaluation 一次、寄 S1 信、Argon 審、04 總結 | 3:00–5:30 |

換手點：A 做完步 0（格式＋`check`）即 commit，B／C 以它為契約；A 做完 epoch 流程後把 `ops.jsonl` 讀寫交 B 接 scan／stall；C 的 `ctl` 殼接 A 的 inbox 契約。全程只有一棵樹在 `ws/hammer/` 跑；三線各自在 scratchpad 跑小測，不開第二全量。資源：arcbatch `--threads 6`、`nice -n 19`、`systemd-run --user --scope -p MemoryMax=16G`；一個 epoch 記憶體 <2G。

## 8. 預算與時間估計

| 項 | 量 | 估時 |
|---|---|---|
| 主跑一 epoch | 48 題 ×100k＋P48 ≤400k，arcbatch | 1～3 秒 |
| gate 留一重搜 | 進料 ≤10 支 × ≤4 對 × 25k | 1～2 秒 |
| 影子跑 | 同主跑；含 `halves` 列時 48 題走 Python（r08 實測 100k 約 1 秒） | 2～5 秒 |
| 一 epoch 合計 | 含 G1、寫檔 | **10～20 秒**；8 epoch ≈3 分 |
| gate-scan | 20 變體 × 3 seed × 4 epoch | ≈8 分 |
| sieve/exclude | 32 × 1 pass | ≈1 分 |
| LTO-SCF∪ | A 折 8 epoch＋B 折 1 pass | ≈3 分 |
| 鑄模 | 1 次 opus 子 agent＋逐段 seed-sub ≤8 段 ×200k | 10～20 分（等待含在 daemon 內） |
| gated evaluation | 400 題一次 | 沿 r08 |

## 9. 預先寫死的判準與「什麼算方向對」

| 代號 | 判準（看結果前寫死） |
|---|---|
| M0 重現 | 相容模式重現 `dec-g1` sha `7aebb3c73f28`；不過則其餘數字一律不報 |
| M1 底線 | 報出的曲線中 `solved_H24` 逐 epoch 不退（回滾次數另報）；`false_pos` 全 0；`llm_calls` 全 0；purity 過 |
| M2 方向對（四中二） | (a) ≥1 條 `incubating` 列由樹自己的判準升 live，`evidence.new_solves` 非空、`by≠user`；(b) ≥1 條 `gate`／`sieve` 列 layer-2 接受且 0 掉題；(c) ≥1 個蠟模→≥1 條 `comb incubating`；(d) 末 epoch H8＋H24 比 epoch 0 多 ≥1 題，或 AUC_L >32 |
| M3 誠實預期 | AUC_L 48（若 `halves` 列被兩段判準升 live——它是 agent-r08 寫的拆法，升降由樹判，04 要分開標）；H24 1→1～2；H8 0～1；蠟模 1～2 個、跨模反合一 0 次；gate-scan 多數變體 Δ0 |
| M4 不算進步 | 只有 `lib_bits`／`nodes` 降（教訓 7）；靠 `add-op --live` 升的分；`incubating` 數膨脹 |
| M5 壞訊號 | 全列 dormant 時 AUC_L <32 → 引擎 bug 非學習訊號，先修再報；回滾 ≥3 次 → 升級門太鬆，收緊 `evidence` 門（新解 ≥2 題）後重跑 |

## 10. 本輪不做

鍛造爐與對手鍛造（r10）；`rewrite` 列與蒸餾；逆推器與 `pipe` 子節點；園區快取；守門搜尋；第三種病人；`up-params`；影子錢；aos-self-opt 抽取（格式已留：`hammer/` 不 import `grow/` 以外的舊樹，收輪可整包抽）；C++ `forbid_ast`（寫信給 S1）；一次鑄 3 題；對兩段判準與 H24 底線本身做搜尋；G4 演化（r08 三 seed 全距 0，主樹預設關，旋鈕保留）。
