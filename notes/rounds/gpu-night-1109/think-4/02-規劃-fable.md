# think-4 02 規劃（fable）

← [01 簡報](01-簡報.md)｜[01a 蒐集](01a-蒐集-sol.md)｜上輪 [代定清單](../think-2/代定清單.md)

## ELI5 結論

現在的尺量的是「樹**已經背了幾題答案**」，不是「樹**學得多快**」：5 題從 epoch 0 就靠庫存積木命中，另 11 題 4 輪都碰不到，所以子代全 20 分。修法：量分前**先把庫存清空**（刪掉副本裡全部 comb 積木，骨架留著），題目換成「活樹**曾經學會**的 16 題」，分數改成連續的「省了多少搜尋位元」。這樣尺量的就是「同一組學得會的題，從零重學要多久」。先拿 6 棵故意改笨的樹試尺：至少 3 棵要被顯著分出、1 棵預期不變的對照不能被誤判，再拿現成 8 個子代驗至少 1 個分得出，尺才算修好。演化缺口（交配同 sha、D27、D18 對照）在尺綠後補；Janet 表示只做往返不做語意。

## 塊 A 量尺（最細）

### A1 量什麼

- **主分 `learn_bits`**（連續，越大越好）：Σ_{e=1..E} Σ_{t∈L′} [log2 B − log2 min(ntf_{t,e}, B)]，只計 `test_ok` 題，未解＝0。E=4、B=50k、16 題時上限 ≈ 4·16·15.6 = 999。不相對 e0（庫存已剝，e0 解出的就是骨架自己的本事）。
- **副分**：`tts_epochs`＝Σ_t 首解 epoch（從未＝E+1；越小越快，ELI5 用）、`auc_L`（舊離散分，留作連續性）、`auc_speed_L`、`cost`、`wall_s`、`eff`＝learn_bits/log2(cost)。
- **門**（不過＝紅、不計分）：`guard-leak` PASS；副本 `hammer.check_root` 0 錯；`stripped_ops` 數＝副本原 comb 數（確認真剝光）；同樹重跑兩次 `learn_bits` 位元組相同（決定論自檢）。

### A2 剝庫、題集、預算

- **剝庫**：副本 `ops.jsonl` 刪全部 `kind=comb`（decomp 全留；gate／route／judge／weight 不動）。只動 `ws/evo/` 副本，基因體與活樹零改動；GA check 不受影響（它查基因體不查副本）。
- **題集 L′（16 題，鍵名仍叫 `L16`）**：活樹 e8 已解的 L16 6 題＋P48 已解 15 題裡依活樹首解 ntf 由小到大取 10 題（易→難梯度給尺解析度）。P 仍清空（D17）；H8／H24 不動。選題清單寫進 `reports/think4-1110/a/taskset-Lp.json`，含每題活樹首解 ntf 供對照。
- **預算**：主 **C50/4**（L=50k、E=4）；試跑 C25/4 當對照。選法：親代＋6 改笨樹各跑兩組（14 跑，≈12 分），取「分出的改笨樹較多」者；同分取快者。D24 鎖預算不變。
- **耗時與並行**：剝庫後 e0 無庫存命中，每題跑滿預算，估單體 C50/4 ≈ 40–60 s（threads=1）。`meter-batch --jobs 4`：4 程序各 `threads=1`，每體獨立父目錄 `ws/evo/meter/<genome_sha>/`（quick 寫 `root.parent/quick.json` 會撞，必須如此）。一代 8 子代 ≤ 4 分鐘；塊 A 全驗收 ≈ 30 跑 ≤ 30 分。
- **GPU**：本塊不用。無整樹介面、e2e 1e6 時 GPU 反慢；GPU 繼續留 N3e／R1 支線。

### A3 故意改笨的樹（6 種，走 quick 直接入口，不必過 GA check）

| 名 | 做法（副本上） | 預期 |
|---|---|---|
| `no-decomp` | decomp 只留 1 個 | learn_bits ↓ ≥40%，tts ↑ |
| `gate-dormant` | 全部 gate status=dormant | 無晉升→曲線平：learn_bits ↓ ≥30%，auc_speed≈0 |
| `route-flat` | route priority 全設同值 | learn_bits ↓ 15–30% |
| `weight-floor` | 節點 weight 全 0.25 | learn_bits ↓ 5–15%（量尺靈敏度地板） |
| `half-budget` | 同樹 L=25k 跑（尺自身對照，非基因體） | learn_bits ↓ ≥30%（高於 log2(25k) 的位元消失＋少解） |
| `judge-high` | stage1 `new_solves_min` 拉到 16 | **預期不變**（judge.py:41 沒讀此欄）→ 陰性對照，若被判顯著＝尺或假設錯 |

### A4 顯著性（快撥決定論 σ_rerun=0）

- 成對 over-tasks bootstrap：每題 d_t＝B.bits_t − A.bits_t，有放回抽 16 題加總，n_boot=2000，σ＝pstdev；z＝Δ/σ。
- **顯著門**：|z| ≥ 2 **且** 兩半題集（依 taskset 順序奇偶分）Δ 同號。σ=0（全 0 或每題差相同）→ `z=null`、不顯著（沿 GA 規則；`think1_meter.compare` 的 σ=0∧Δ≠0=true 規則廢，改呼叫 `noise.compare`）。
- 多 seed：hammer 無隨機種子，不造假 seed；「兩半同號」就是穩健軸。若 16 題仍 degenerate 多，翻案點＝題集擴到 24。

### A5 驗收條（任一不過＝紅）

1. 親代 C50/4 重跑 2 次 `learn_bits` 相同；單體 wall ≤ 60 s。
2. 6 改笨樹中 ≥ 3 棵 z ≤ −2 且方向符預期；`judge-high` **不**顯著。
3. 現成 g1 8 子代（`ws/evo/pop/g1/*/tree.json`）**至少 1 個**與親代 |z| ≥ 2。
4. 門全綠：leak PASS、check_root 0 錯、stripped_ops 數對、`conservation` 守恆。
5. `reports/think4-1110/a/accept.json` 列全部數字；演化產物留 `ws/evo/meter/`，不進 git。

### A6 落檔

- 新 `src/arcagi/treegen/meter.py`：`strip_comb(copy_root) -> stripped_ops`、`per_task_bits(root, E, B)`、`score(root) -> dict`、`compare(a, b)`（呼叫 noise 的成對 bootstrap，metric 參數化）、`halves_agree`。
- 新 `src/arcagi/treegen/dumb.py`：6 道配方 `make(parent_tree, recipe, out)`，只產副本。
- 改 `quick.py`：`prepare` 加 `strip: bool`、`taskset_override: path`；`_per_task` 加 `first_epoch`、`seconds`、`bits`（讀 solutions.jsonl 既有欄）。schema 升 `think2-quick/2`（noise `_load` 同步認）。
- 改 `noise.py`：`_paired(a, b, metric="auc"|"bits")`。改 `fitness.py`：CFG 加 `L=50000, strip=True, taskset="Lp"`，`comparison` 用 bits，`eff` 重定義。`select.py` 排序鍵改 `learn_bits`。
- `cli.py` 子指令：`meter <tree|dir> --out --L --epochs --strip --taskset --threads`、`dumb <parent> --recipe --out`、`meter-batch --jobs 4 <list>`、`meter-accept --parent --dumb --children --out`。
- 輸出 `meter.json`（schema `think4-meter/1`）：`genome_sha, cfg{L,epochs,strip,taskset_sha,threads}, stripped_ops[], scores{learn_bits,tts_epochs,auc_L,auc_speed_L,cost,wall_s,eff}, per_task{tid:{bits[],ntf[],solved[],first_epoch,seconds[]}}, curve[{epoch,solved,logcost,bits}], gates{leak,check_root_errors,conservation}`。compare 輸出：`d_learn_bits, sigma, z, significant, halves_agree, degenerate, n_tasks`。
- 測試 `tests/treegen/test_meter.py`：剝庫數、bits 公式（手算 3 題）、σ=0 不顯著、兩半同號。

## 塊 B 演化缺口（簡要）

1. **交配同 sha**：`crossover.py:66` 回傳前比 `child_sha ∈ {a_sha, b_sha}`→重抽 ≤ 5 次、仍同則回 `collapsed=true`；`ga.py:200–209` 交配分支加入同一 `seen` 檢查並記 `duplicate_crossover`。驗收：`ga-fake` 1 代無子代 sha 等於任一親代；g1 的 X1／X3 案例回放被擋；測試 2 條。
2. **D27 活動量**：`ledger` 加 `--weights static|activity`（預設 static 不變），activity 直接呼叫 `fitness.activity_credit`。驗收：親代 quick 兩模式 `ledger-check` 守恆皆過，差異表進 `reports/think4-1110/b/weights.json`。另補 `health.py:54` 輸出 `dormant-active` 建議（mutate 已有該臂）。
3. **D18 對照（等塊 A 綠）**：`ga --arm guided|uniform|mixed`；跑 1 代 8 子代＝4 guided＋4 uniform，meter 評分，比兩臂 Δlearn_bits 平均與各自顯著數。判法：guided 平均 ≤ uniform 且 |z| ≥ 2 → 關引導（D18 翻案點）；否則留 80/20。產物 `reports/think4-1110/b/arms.json`。

## 塊 C Janet 表示＋嵌套／節點池（方向）

- 方向：`tree.json`（aos-tree/1）↔ Janet S 式一對一；節點＝`(node :id .. :kind .. :children [..])`、子樹以 `$ref` sha 引用（接 D25 refs），於是「樹是積木、節點是積木」在表示層成立。Janet 側照 janet-lab 慣例（模組一夾、init.janet re-export、`parse-all`、`json/decode` 保 nil 的參數要定）；aos `extras/langs/janet` 不存在，本輪不依賴。
- 第一步（半天）：`src/arcagi/treegen/sexpr.py` 印出＋讀回；驗收＝tree.json→.janet→tree.json **位元組相同**、`genome_sha` 不變、janet 端 `parse-all` 讀得回同節點數。**不做**執行語意、不評分。
- 節點池：只寫對照表（treegen credit/health ↔ node-pool 的報銷／分紅／房租／退休建議），記 N/03 的「公式反向獎懲」警告；不寫碼。

## 方向題（隊長照推薦代定）

1. **剝庫方式**：全剝 comb（**推薦**）vs 只剝命中 L′ 的。後果：op status／刪 op 兩個突變面在尺上失明（分數相同→不被選，無害）；D19 op_bank、M4／M6 退出本尺。好處：不依賴 evidence 準確、洩漏歸零。
2. **主分**：`learn_bits`（**推薦**）vs `tts_epochs` vs 留 `auc_L`。後果：select／eff 全改鍵；auc_L 只回報。
3. **預算**：C50/4（**推薦**，試跑定案）vs C25/4 vs C50/6。後果：單體 40–60 s；一代 ≤ 4 分。
4. **題集**：L′＝6 L 已解＋10 P 已解（**推薦**）vs 原 L16。後果：原 L16 10 題未解題退出尺（4 輪學不到，只貢獻 0）；P 題當學習題＝放棄 P 當積木池（D17 已清，無新洩漏）；`new_solves` 不可與活樹直接比（D17 已註）。
5. **顯著門**：|z|≥2＋兩半同號（**推薦**）vs 單 |z|≥2 vs |z|≥3。後果：少假陽性；σ=0 一律不顯著，兩套 compare 規則統一。

## 風險

- 空庫 4 輪學不到→全 0（反向 degenerate）：備援 C50/6；再不行退「只剝命中」。
- hammer 遇空 comb 的 `ops.jsonl` 崩：活樹 e0 本就 0 comb，應可；崩則退「只剝命中」。
- P 題進 L16 鍵：formats／judge 若寫死 16 題或集合名，保 16 題規避；崩則退原 L16＋C50/6。
- 多程序並行只靜態核過：先 2 程序試，撞檔即降 1。
- 剝庫後守門一 `tainted` 診斷轉 PASS，要在 accept 註明（D22）。
- `half-budget`／`judge-high` 是尺的對照不是基因體，不得混進族群。

## 這輪不做

GPU 整樹核；改 `src/arcagi/hammer/` 與活樹；judge.py:41 讀 stage1（hammer 原始碼）；Janet 執行語意；op_bank／M4／M6；多代演化與族群放大；偽 seed；活樹 L16 的 10 未解題攻堅。
