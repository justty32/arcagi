# think-2 規劃（fable）：把整棵 aos 樹變成可序列化、可演化、可歸責的積木

← [簡報 01](01-簡報.md)｜[蒐集 01a](01a-蒐集-sol.md)｜[代定清單](代定清單.md)

## 0. ELI5 結論

hammer 這棵樹今天像一間正在營業的店：帳本、庫存、客人腳印（epochs／ledger／witness）和「店的設計圖」（frozen、ops 的 payload、nodes 的 entry）全攤在同一地板上。要讓「整棵樹」當遺傳個體，第一步不是演化，而是**先把設計圖從腳印裡抽出來印成一張 JSON（基因體）**，再證明這張圖能原樣蓋回一間一模一樣、跑起來結果相同的店（往返一致）。圖上重複的零件只畫一次、其他地方寫「見第幾頁」（`$ref`＋內容雜湊）。

有了圖才能做三件事：(a) 改圖＝突變／換頁＝交配，合不合法先過 `check`，好不好用拿「快撥樹」（縮小預算的同一棵店）跑一次量 `auc_L／cost`，拿雜訊尺判顯著；(b) 每一輪的分數差先記在頂層，再**像發薪水一樣逐層分給節點與子樹**（功勞／責任同一張表、守恆），拿到責任的子樹就用上輪的計分卡做體檢並決定改哪裡；成本帳改成任意 key 的 JSON，時間與 token 同帳換錢；(c) Argon 的兩條警告寫成兩支守門程式：P 池題不准當造積木原料、任何「收／升／退」門檻不准用格子相符率。

判準是「樹搜得更快」：塊 2 的快撥樹＋雜訊尺就是尺，其餘每塊都要能在尺上顯示 Δ。GPU 這輪只能當旁路（題目特性），不能評估 hammer 的 AST——這點要誠實寫進風險。

## 1. 分塊規劃

通用規則（gpt sol 施工）：
- 程式碼放 arcagi 新子夾 `src/arcagi/treegen/`（新套件）與 `scripts/think2_*.py`；演化中間產物一律放 `/home/lorkhan/code/playground-arc1/ws/evo/`（不進 git）；報告放 `reports/think2-1109/`。
- 活樹 `ws/hammer/` 既有檔**一個都不改**；只讀。
- 每塊驗收＝一條命令印一個 JSON `{"block":…,"pass":bool,"checks":[{"name":…,"got":…,"want":…,"ok":bool}]}`，寫到 `reports/think2-1109/<塊>/accept.json`。gpt 不寫測試，驗收就是這條命令實跑。

### 塊 1　樹⇄JSON 往返工具（必做、先做）

**做什麼**：`export`：把一棵 aos 樹的「定義部分」收成一份 `tree.json`；`import`：從 `tree.json` 蓋出一棵新樹；`diff`：比兩棵樹／兩份 JSON。對活樹 hammer 實跑 tree→json→tree→json，兩份 JSON 內容相同。

**基因體邊界**（寫死在 `treegen/boundary.py`，可被 `--profile` 覆蓋）：
- 進基因體：`_metainfo.json`、`frozen.json`、`ops.jsonl` 的定義欄（`id,kind,status,payload,sig,mdl_bits,parent_route,by,born`）、`nodes/*/_metainfo.json`、`truth/**`（屬設定、含 H8／H24 題號、標 `sealed`）、`ctl`／`_view.sh`／`README.md` 以存根 `{"$file":"<相對路徑>","sha1":…,"mode":"755","bytes":n}`（內容另存 `files/<sha1>`）。
- 不進：`epochs/`、`live/`、`foundry/`、`tmp/`、`RUN`、`ledger.jsonl`、`think1/`、`nodes/*/_witness.jsonl`、`nodes/*/{inbox,outbox}/`、`ops/<id>/`（投影，import 時由 ops.jsonl 重建）。
- ops 的狀態欄（`evidence,ttl,env_hash,blamed_by,tried_env_hashes`）抽到側車 `state.json`；import 時若無側車就用 `formats.new_op` 的預設值填回（事實核對：`new_op` 已定義全欄預設）。

**新檔案**：
- `src/arcagi/treegen/{__init__,boundary,export,import_,refs,diff,cli}.py`
- `scripts/think2_roundtrip.py <tree_root> --out <dir>`（一鍵：export→import→export→diff→accept.json）
- 產物：`/home/lorkhan/code/playground-arc1/ws/evo/rt/hammer/{tree.json,state.json,files/,tree2/,tree2.json,diff.json}`

**資料格式 `tree.json`**：
```
{"schema":"aos-tree/1","name":"hammer","exported_from":"<abs path>","at":"<iso>",
 "boundary_profile":"hammer-v1","genome_sha":"<sha1 of canonical tree+defs>",
 "defs":{"<sha12>":{…子樹…}},           # 共用子樹，內容定址
 "tree":{"_metainfo.json":{…},"frozen.json":{…},
         "ops.jsonl":[{…定義欄…}],        # 依 id 排序
         "nodes":{"solve":{"_metainfo.json":{…}},…},
         "truth":{"train":{…},"cal":{…},"$sealed":["H8","H24"]},
         "ctl":{"$file":"ctl","sha1":…,"mode":"755","bytes":n}},
 "stats":{"files":n,"bytes":n,"refs":n,"defs":n}}
```
- 共用子樹規則（`refs.py`）：任何 object／array 子樹 canonical 長度 ≥ 64 bytes 且出現 ≥ 2 次 → 搬到 `defs[sha12]`，原位改 `{"$ref":"#/defs/<sha12>"}`；可用 `--dedup off` 關閉。import 時展開。`$ref` 只允許指 `#/defs/`，不允許相對路徑（避開「搬位置改行為」）。
- canonical＝`json.dumps(sort_keys=True, separators=(",",":"), ensure_ascii=False)`；寫檔沿用 `formats.write_json`（indent=1）／`write_jsonl`。

**量法**：三層一致。L0 位元組：`sha1(tree_root 內每個基因體檔)` 對照（只回報）；L1 內容：`diff.json` 的 `n_diff`；L2 行為：對 `tree2/` 跑塊 2 快撥一次，`solutions.jsonl` 的 solved 題集合與 `curve.csv` 的 `solved_L,logcost_L` 與原樹快撥相同。

**驗收門檻**：L1 `n_diff == 0`；`defs` 展開後與未去重 export 內容相同（`--dedup off` 對照 `n_diff == 0`）；`truth/` 的 H8／H24 `ids_sha` 與 `frozen.holdout.*.sha` 一致；L0 不同檔數回報（預期只有 `ops/<id>/` 投影與 key 順序無差，因 hammer 本身就 sort_keys）；L2 在塊 2 完成後補跑一次 `Δ=0`。export＋import 單次 wall ≤ 5 s。

**工時**：gpt 4～6 h（含 diff 與 CLI）。**GPU**：不適用。

### 塊 2　評判基準：快撥樹＋雜訊尺＋兩支守門

**做什麼**：把「量樹搜得多快」做成一條命令；再把 Argon 兩條警告做成會印 FAIL 的程式。塊 4 的適應度、塊 3 的頂層 Δ 都依賴它，所以排第二。

**新檔案**：
- `scripts/think2_quick.py <tree.json> --out <dir> [--L 50000 --P0 10000 --epochs 6 --subset L16]`：import 基因體→覆寫 `frozen.budgets`／`taskset` 子集→用 `ctl` 跑 N epoch→呼叫 `think1_meter.py` 寫 `curve-summary.json`→寫 `quick.json`。
- `scripts/think2_noise.py <quick_dir_A> <quick_dir_B>`：決定論檢查（Δ 必須 = 0）＋ 題目 bootstrap 1000 次 → `noise.json`。
- `src/arcagi/treegen/guards.py` ＋ `scripts/think2_guard.py <tree_root|tree.json> --rules guards.json`
- `reports/think2-1109/guards/thresholds.json`（門檻登錄表，人手維護）
- 產物：`/home/lorkhan/code/playground-arc1/ws/evo/quick/<genome_sha>-<cfg>/{tree/,quick.json,noise.json}`

**資料格式**：
- `quick.json`：`{"genome_sha","cfg":{"L","P0","epochs","subset"},"wall_s","auc_L","auc_speed_L","cost","eff","solved_L_final","logcost_L_final","per_epoch":[…],"guards":{"leak":"PASS|FAIL","threshold":"PASS|FAIL"}}`
- `noise.json`：`{"determinism_delta":{"auc_L":0,"cost":0},"n_boot":1000,"seed":…,"sigma_auc_L","sigma_cost","sigma_eff"}`
- 守門一（偷看考卷）`guards.json.leak`：讀 `truth/`、`frozen.taskset`，算 `P∪H8∪H24`；規則：每列 op 的 `payload.src_tasks`（comb）或 `born.src`（若有）∩ 禁池 = ∅；`judge` 升級依據 `evidence.new_solves` 若全部落在禁池 → 標 `tainted`。輸出 `{"rule":"no_build_from_P","violations":[{"op_id","tasks":[…],"pool":"P"}],"tainted_ops":[…]}`。**現況會 FAIL**（簡報 §4：gate_ids=L16∪P）——這是預期，用來證明守門有牙。
- 守門二（相符率不准當門檻）：`thresholds.json` 每列 `{"site":"<file>:<func>","metric":"pixel_acc|train_exact|…","purpose":"rank|diag|accept|promote|retire","tag":"ok|forbid"}`；程式對 `src/`、`scripts/` grep `pixel_acc|cell_acc|match_ratio|match_after`，每個命中必須登錄；`purpose ∈ {accept,promote,retire}` 且 metric 為相符率類 → FAIL。初始登錄至少 3 個已知位置（`solvers/search.py` near_miss、`blocks/pool/ledger.py` 梯度排序、`scripts/taxonomy_failsample.py`），皆 `rank|diag`。

**量法**：wall_s；σ；守門 FAIL 數。

**驗收門檻**：快撥單跑 wall ≤ 180 s（量 L=50k／6 epochs 與 L=25k／4 epochs 各一次，記兩者 wall 與 σ）；兩次同設定 `determinism_delta == 0`；`sigma_auc_L ≤ 2`（上輪門檻，超過要寫原因）；守門一對活樹印 FAIL 且 violations ≥ 1；守門二對 repo 印 PASS 且未登錄命中 = 0；對塊 1 的 `tree2/` 跑快撥 Δauc_L = 0（補塊 1 的 L2）。

**工時**：gpt 5～7 h。**GPU**：不適用（快撥是 CPU 枚舉；bootstrap 用 numpy 即可）。

### 塊 3　開放成本帳＋逐層分功勞／責任＋計分卡體檢

**做什麼**：把寫死的成本欄換成任意 key 的 JSON 帳；把頂層每輪 Δ（來自塊 2 的尺）像薪水一樣沿「樹→節點→op／子樹」分下去，守恆；拿到責任的子樹呼叫上輪 `think1_audit` 當體檢，產生「改哪裡」的建議。先離線對 hammer 既有 epochs 0..8 跑通，不接線上。

**新檔案**：
- `src/arcagi/treegen/{cost,credit,health}.py`
- `scripts/think2_ledger.py <tree_root> --out <dir>`（把現有 `ledger.jsonl`＋`curve.csv` 轉成開放帳 `cost.jsonl`，並算 `credit.jsonl`、`health.json`）
- `reports/think2-1109/cost/rates.json`（換錢率）
- 產物：`/home/lorkhan/code/playground-arc1/ws/evo/ledger/hammer/{cost.jsonl,credit.jsonl,health.json}`

**資料格式**：
- `cost.jsonl` 每列：`{"t","epoch","who":"hammer|nodes/solve|ops/comb_g1_x","cost":{"wall_s":…,"evals.body":…,"evals.shadow":…,"llm.calls":…,"llm.tokens":…},"note":…}`。規則：key 為點分路徑、任意新增；`price(cost, rates, keys=None)`＝Σ rate[k]×cost[k]，只對 `keys` 子集算時其他 key 保留不計；無 rate 的 key 計 0 但保留。`rates.json` 初值依 aos 定稿：`{"llm.tokens":0.001,"wall_s":0.1}`（千 token＝1、秒/10）。成本結構本身是 JSON 所以可被塊 4 突變（這輪只開放 `rates`，不開放 key 結構）。
- `credit.jsonl` 每列：`{"epoch","from","to","score":-1..1,"amount","why":{"d_auc_L","d_cost","new_solves":[…],"blamed_by":…}}`。分法：頂層 amount＝`d_eff`（塊 2 尺）；留 20% 給頂層；80% 先按 `evidence.new_solves` 歸 op，無歸屬部分按 `nodes/*/_metainfo.weight` 分給節點；負 Δ 時依 `blamed_by` 與 `idle_epochs` 分責。守恆：Σ(to≠root) + root = 頂層 amount。
- `health.json`：`{"epoch","nodes":{"solve":{"ok":bool,"verdicts":{"keep":n,"retire":n,…},"audit_path"}}}`——直接重用 `think1_audit.py` 的 `verdict` 欄。

**量法**：守恆殘差；覆蓋率（每個 live op 有 ≥1 credit 列）；體檢完成節點數。

**驗收門檻**：對 hammer epochs 1..8 跑通；每輪守恆殘差 ≤ 1e-6；live op 覆蓋率 100%；7 個節點 health 全有值；`price(cost, rates)` 對 epoch 總和與 `think1_meter` 的 `cost` 相差 ≤ 1%（舊欄換算到新帳不掉數）；再隨便加一個新 key（如 `gpu.sec`）重算不報錯。

**工時**：gpt 5～6 h。**GPU**：不適用。

### 塊 4　整棵樹當遺傳個體：運算子＋合法性＋適應度

**做什麼**：以塊 1 的 `tree.json` 為個體，實作突變／交配／`check`／選擇，一代族群用塊 2 快撥評分、用塊 3 的 credit 當子樹級適應度。先跑 1 代 8 個體證明管線通，不追分數。

**新檔案**：
- `src/arcagi/treegen/{mutate,crossover,check,select,ga}.py`
- `scripts/think2_ga.py --parent <tree.json> --pop 8 --gens 1 --out <dir> --seed 0`
- 產物：`/home/lorkhan/code/playground-arc1/ws/evo/pop/g<gen>/<ind_id>/{tree.json,parents.json,fit.json}`、`ws/evo/pop/hall/`（菁英存檔）、`ws/evo/pop/fit_cache.jsonl`（`genome_sha→fit`）

**運算子**（全部只碰基因體 JSON，不碰 Python 入口）：
- 突變 M1 參數抖動：`frozen.budgets.*`、`frozen.judge.*`、gate `payload.params.*`、route `priority`（各有上下界表 `bounds.json`）；M2 op `status` live↔dormant；M3 刪一個非 gate op；M4 comb 換體：從族群 comb 庫挑 `sig` 相同者替換 `payload.body`；M5 節點 `weight`。
- 交配 X1 同 kind 的 ops 子集互換；X2 整個 `nodes/<k>` 子樹互換（必經 `$ref`，共用自動被記下）；X3 `frozen.judge` 區塊互換。
- `check`：每列過 `formats.check_op`；`parent_route` 存在；decomp `name` 在已知集；comb body 無未綁定 `$0`（lam 外出現即非法，對應 Argon 的懸空 AST）；`bounds` 內；**硬規則**：`truth/` 與 `frozen.holdout` sha 不變、`$sealed` 不可碰；守門一對子代 PASS（`--subset L16` 下 src_tasks ⊆ L16）。
- `parents.json`：`{"ops":[{"op":"M1","path":"/tree/frozen.json/budgets/L","from":…,"to":…}],"parents":[sha,…]}`。
- `fit.json`：`{"genome_sha","F0":{"legal":bool,"mdl_bits_total","n_live"},"F1":{"auc_L","cost","eff","wall_s","sigma_auc_L"},"credit_by_subtree":{"nodes/solve":…},"significant":bool}`；F0 免費先篩，F1 才跑快撥；`fit_cache` 命中就不跑。
- 選擇：(μ+λ) 菁英 2，錦標賽 3；不自動刪個體，輸者移 `hall/` 保留（見 §3 第 3 題）。

**量法**：子代合法率；每代 wall；最佳子代 `eff − parent.eff` 以 σ 判顯著；共用子樹數（`stats.refs`）。

**驗收門檻**：1 代 8 子代全部 `check` 通過（非法的在產生時重抽，重抽 ≤ 20 次）；8 次快撥總 wall ≤ 30 min；`fit_cache` 命中 ≥ 1（故意放一個複製個體）；至少 1 子代 `eff ≥ parent.eff − sigma`；所有個體 `holdout sha` 不變；`ws/evo/` 不在 `git status` 出現（在 `.gitignore` 旁新增 `ws/evo/` 不需要——playground 本就不是 arcagi repo，驗收改為 `git -C arcagi status --porcelain | grep evo` 為空）。

**工時**：gpt 8～10 h（最大塊，可拆兩晚）。**GPU**：**這輪不行**。hammer comb body 是 list-of-list AST（`map/lam/append/reverse`），GPU 現有 `gpusearch`／GP 只吃格子 `DStep` 字母表（簡報 §5），沒有評估 hammer AST 的核；寫一支 ≤3 GB 的 AST 評估核是另一個獨立塊（見方向題 4）。GPU 旁路：快撥時順帶跑 `gpusearch --tasks <L16>` 收題目特性寫 `ws/evo/features/<task>.json`，不進適應度。

### 塊 5　Janet 寫法（塊 1 過了才做；可延後）

**做什麼**：`tree.json` ⇄ `tree.janet`，程式即資料的第二種寫法；不碰 Lua／Python。

**新檔案**：`src/arcagi/treegen/janet.py`、`scripts/think2_janet.py <tree.json> --out tree.janet --back tree.back.json`；本機 `~/.local/bin/janet` 只用來 `janet -e` 讀回驗證。

**格式**：`(tree "hammer" (file "_metainfo.json" {…}) (dir "nodes" (dir "solve" (file "_metainfo.json" {…}))) (ref "#/defs/abcd"))`；JSON `null` → `:null` 關鍵字、key 一律字串、陣列用 `@[]`（簡報 §3：null 與 key 次序會有差，所以回程走 canonical 比內容）。

**驗收**：JSON→Janet→JSON `n_diff == 0`；`janet -e '(import ./tree)'` 能載入（語法合法）；wall ≤ 1 s。**工時** 2～3 h。**GPU** 不適用。

### 三條主題對照

(a) 往返＋引用＋遺傳個體 → 塊 1、4、5；(b) 分層改進＋計分卡體檢＋開放成本帳 → 塊 3（接塊 2 的尺）；(c) 快撥樹＋雜訊尺＋兩支守門 → 塊 2。施工順序 1→2→3→4→5；塊 3 與塊 4 的運算子部分可平行。

## 2. 使用者交 fable 定的三題（附意見）

**1. 往返一致判準：以「內容」為門、「行為」為驗收、「位元組」只回報。**
理由：hammer 自己就用 `sort_keys` 寫檔，位元組差只會來自 key 順序與投影檔，比位元組會把無害差當錯；但只比內容又抓不到「搬位置改行為」（相對路徑、cwd），所以 L2 行為對照必做一次、而且在每次改運算子集合時重跑。行為比對物＝快撥的 `solved_L` 集合＋`logcost_L`，不比 wall。附帶：`$ref` 禁用相對路徑，從結構上消掉一類行為差。

**2. 共用子樹改前要不要複製：要，且自動——內容定址＝天然 copy-on-write。**
`defs` 以內容 sha 為 key，任何對 `$ref` 目標的突變都產生新 sha、只重指本個體，其他引用者不受影響；「共用」是被偵測出來的（兩處內容相同），不是被維護的。這和 aos 定稿「複製只在兩個上級連續 2 epoch 給相反分數時由上級出錢」不衝突：那條講的是節點池裡的實體節點，這裡講基因體表示。「就地改 def 使全體跟著變」的傳播型運算子這輪**禁用**，等有 credit 資料再開。

**3. 自動淘汰與否：族群層自動選、節點層不自動退。**
整棵樹個體的選擇是 GA 本份（輸者進 `hall/` 不刪檔）；但樹內節點／op 的退休只寫 `retire_suggest.jsonl` 建議（來自塊 3 health 的 `verdict=retire` 連 3 輪），人按才退、可復活，與 aos 定稿一致。理由：aos 實測「最貴節點先餓死、零花費腳本永不退」，自動退會先退掉最有用的貴節點。磁碟由人定期清 `hall/`。

## 3. 方向題（≤5，隊長照推薦先做）

1. **`gate_ids=L16∪P` 的洩漏要不要改 hammer 原始碼？**
推薦：這輪只做外部守門（塊 2）印 FAIL，不改 `epoch._main_run`；另開一張待辦「`frozen.gate_pools`（預設沿用現狀以保活樹行為不變，快撥設 `["L16"]`）」交白天的人。後果：活樹繼續洩漏到白天；快撥若不改原始碼也會洩漏，所以塊 4 適應度會虛高——用守門一的 `tainted_ops` 把虛高的 `new_solves` 剔除後再算 `eff`（寫進 `quick.json.guards`）。

2. **快撥預算用哪組？**
推薦：塊 2 兩組都量一次（50k/6 依 Argon、25k/4 依原案），取 `sigma_auc_L ≤ 2` 且 wall 最小者；兩者皆 >180 s 就縮 `taskset` 到 L16 全集不含 P。後果：預算越小、造詞越「失明」（Argon），所以塊 4 的 Δ 要同時報 σ。

3. **`ops.jsonl` 要不要在活樹裡物理拆成定義／狀態兩檔？**
推薦：不拆活樹，只在基因體表示拆（export 剝離、import 由側車或 `new_op` 預設回填）。後果：活樹零改動；代價是 import 回來的 `evidence` 是空的，快撥從乾淨狀態起跑——這正是我們要的。

4. **GPU 這輪投不投「hammer AST 評估核」？**
推薦：不投；GPU 只做題目特性旁路。後果：GA 評估被 CPU 綁在約每小時 20～30 個個體；如果塊 4 跑通後想放大族群，再立 `native/gpu/ast/` 為下一輪塊，顯存目標 ≤1 GB。

5. **族群起點只用 hammer，還是也混 `aos/seedlib` 的樹？**
推薦：只用 hammer 單親＋突變。後果：多樣性低、第一代差異小，但邊界只要一套 `boundary_profile`，gpt 做得完；混樹要先給每棵樹寫邊界檔。

## 4. 風險與不做的事

**風險**
- 守門二是 grep 等級的 lint，不是證明：漏登錄一個新寫法就漏；補救是每塊驗收都附跑一次守門。
- 快撥若 >3 min，塊 4 一代 8 個體就要半小時，夜間只能跑 1～2 代——所以塊 4 驗收只要求「管線通」。
- 內容定址去重可能把「碰巧相同」的子樹綁成共用（例如 7 個 node 的 `reads` 都是 `["ops.jsonl","truth/train"]`）；交配 X2 時兩個節點會一起換。可用 `--dedup off` 對照，塊 1 驗收已含。
- gpt 可能把狀態欄漏剝或把 `truth/` 當執行期丟掉；塊 1 的 holdout sha 檢查就是為此。
- 塊 3 的分法（20%／80%、按 new_solves）是借 aos 定稿的常數，沒有證據它能改善搜尋；這輪只驗守恆與覆蓋，不驗效果。

**不做**
- 不改活樹任何既有檔、不改 hammer 原始碼（含洩漏修法，見方向題 1）。
- 不演化 Python 節點入口（`entry` 字串不在突變範圍）；不做 Lua／Python 基因體寫法。
- 不做 def 就地傳播型運算子；不自動退休節點；不自動刪個體檔。
- 不寫 GPU AST 核；不碰 ≥3 GB 顯存；不把 GPU 題目特性接進適應度。
- 不把 `pixel_acc` 從現有排序／診斷位置拔掉——只登錄、只禁門檻用途。
- 中間產物全在 `/home/lorkhan/code/playground-arc1/ws/evo/`，不 commit；沉澱物只有 `src/arcagi/treegen/`、`scripts/think2_*.py`、`reports/think2-1109/`。
