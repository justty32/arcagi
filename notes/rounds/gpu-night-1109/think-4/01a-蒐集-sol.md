# think-4 01a 蒐集（sol）

唯讀蒐集完成；未修改檔案、未跑快撥、未新增測試或佐證檔。以下只列來源、實際紀錄與程式行為，不下設計結論。

外部路徑縮寫：

- **H**＝`/home/lorkhan/code/playground-arc1/ws/hammer`
- **E**＝`/home/lorkhan/code/playground-arc1/ws/evo`
- **J**＝`/home/lorkhan/repo/langs/janet-lab`
- **N**＝`/home/lorkhan/repo/simple_tools/aos/proto8/thinking/2026-11/08/node-pool`

## 1. 快撥 auc_L、旋鈕、題集與實際逐題數字

**prepare／run 的設定。** [quick.py:71](/home/lorkhan/repo/arcagi/src/arcagi/treegen/quick.py:71)、[quick.py:95](/home/lorkhan/repo/arcagi/src/arcagi/treegen/quick.py:95) 摘錄：`frozen["budgets"].update(L=L, epochs=epochs)`；`taskset["P"] = []`。副本承接來源樹的題集，覆寫 L／epochs，預設清空 P；`L > 0`、`epochs >= 0`。[quick.py:166](/home/lorkhan/repo/arcagi/src/arcagi/treegen/quick.py:166) 限制 `threads` 為 1～4，再傳入 `epoch.run_tree(..., backend="native", holdout=True)`。

相關性：L 是搜尋節點預算，epochs 是演化輪數；threads 是底層搜尋並行度，沒有在此改題集大小。

**auc_L 的公式。** [quick.py:146](/home/lorkhan/repo/arcagi/src/arcagi/treegen/quick.py:146) 摘錄：`for n in range(1, epochs + 1)`、`solved = int(bool(solution["test_ok"]))`、`item["auc"] += solved`。[think1_meter.py:69](/home/lorkhan/repo/arcagi/scripts/think1_meter.py:69) 摘錄：`auc_l = sum(int(curves[e]["solved_L"]) for e in scored)`；[quick.py:199](/home/lorkhan/repo/arcagi/src/arcagi/treegen/quick.py:199) 還會核對逐題 auc 加總等於摘要 auc_L。

相關性：這是 epoch 1～E 解題數的離散加總；epoch 0 是基線，不計入 auc_L。

**題集來源與數量。** [H/truth/train/taskset.json:2](/home/lorkhan/code/playground-arc1/ws/hammer/truth/train/taskset.json:2) 的 `L16` 實有 **16 題**，同檔 `P` 有 48 題。[H/frozen.json:46](/home/lorkhan/code/playground-arc1/ws/hammer/frozen.json:46) 摘錄：`"path": "data/r09/taskset.json"`、`"p_key": "P48"`。[formats.py:274](/home/lorkhan/repo/arcagi/src/arcagi/hammer/formats.py:274) 將原始題單的 `learn／holdout／holdout24／P48` 映射成 `L16／H8／H24／P`；實際題目網格由 [grow/curve.py:66](/home/lorkhan/repo/arcagi/src/arcagi/grow/curve.py:66) 從 `data/ARC-AGI/data/training/` 載入。

相關性：L16 是 16 個 training 題號；H8／H24 是這套實驗另切的保留池名稱。

**20 不是全解滿。** [fitness.py:12](/home/lorkhan/repo/arcagi/src/arcagi/treegen/fitness.py:12) 摘錄：`CFG = {"L": 25000, "epochs": 4, "clear_p": True}`。[E/pop/g0/parent/quick/quick.json:32](/home/lorkhan/code/playground-arc1/ws/evo/pop/g0/parent/quick/quick.json:32) 的 epoch 0～4 都是 `solved_L: 5`。逐題紀錄顯示親代與八份子代輸出都固定解出：

`68b16354、1e0a9b12、ce4f8723、496994bd、d10ecb37`。

因此 **20＝5 題 × 4 個計分 epoch**；全部 16 題每輪都解出才會是 **64**。八份子代中有三份命中快取，並非八次獨立快撥，見 [b4/accept.json:25](/home/lorkhan/repo/arcagi/reports/think2-1109/b4/accept.json:25)。

相關性：現象是這批變體沒有改變逐題解出集合，不能稱為題集全解飽和。

**已找到會變動的實際數字。** 下表數字分別摘自各份 `quick.json:3、:20、:21`：

| 個體與來源 | auc_L | auc_speed_L | cost | eff |
|---|---:|---:|---:|---:|
| [親代:3](/home/lorkhan/code/playground-arc1/ws/evo/pop/g0/parent/quick/quick.json:3) | 20 | 17.716 | 7,294,813 | 2.7417 |
| [子代 1：bb25cbafd96e:3](/home/lorkhan/code/playground-arc1/ws/evo/pop/g1/1_bb25cbafd96e/quick/quick.json:3) | 20 | 17.712 | 7,340,734 | 2.7245 |
| [子代 2：095e8f1b0f99:3](/home/lorkhan/code/playground-arc1/ws/evo/pop/g1/2_095e8f1b0f99/quick/quick.json:3) | 20 | 17.988 | 7,297,695 | 2.7406 |

逐題短摘錄：

- [親代 quick.json:295](/home/lorkhan/code/playground-arc1/ws/evo/pop/g0/parent/quick/quick.json:295)：`d10ecb37` 的 `nodes_to_first = [1394,1338,1338,1338]`。
- [子代 1 quick.json:295](/home/lorkhan/code/playground-arc1/ws/evo/pop/g1/1_bb25cbafd96e/quick/quick.json:295)：同題變成 `[1392,1336,1336,1336]`。
- [親代 quick.json:145](/home/lorkhan/code/playground-arc1/ws/evo/pop/g0/parent/quick/quick.json:145) 與 [子代 2 quick.json:145](/home/lorkhan/code/playground-arc1/ws/evo/pop/g1/2_095e8f1b0f99/quick/quick.json:145)：`68b16354` 從 `[13,13,13,13]` 變成 `[14,14,14,14]`。

相關性：auc_L 相同時，現有輸出確實仍保留節點數、速度摘要與成本的差異。

## 2. 替代量法、未解題與預算邊緣題

**auc_speed_L 與 logcost。** [think1_meter.py:85](/home/lorkhan/repo/arcagi/scripts/think1_meter.py:85) 摘錄：`sum(base - float(curves[e]["logcost_L"]) for e in scored)`。[grow/pool.py:100](/home/lorkhan/repo/arcagi/src/arcagi/grow/pool.py:100) 的逐題成本為：

- 未解／無首解節點：`log2(B)`。
- 已解：`log2(max(1, min(nodes_first, B)))`。
- epoch 0 已解題，之後最多計 2 bits 的加速收益，見同檔 `capped()`。

相關性：它可反映解題數不變時的搜尋量變化，但量的是相對各個體自己 epoch 0 的改善。

具體例子：[親代 quick.json:36](/home/lorkhan/code/playground-arc1/ws/evo/pop/g0/parent/quick/quick.json:36) 的 logcost 為 `217.946 → 213.517`；[子代 2 quick.json:36](/home/lorkhan/code/playground-arc1/ws/evo/pop/g1/2_095e8f1b0f99/quick/quick.json:36) 為 `218.121 → 213.624`。後者 auc_speed 較高，但最終 logcost 也較高。

相關性：auc_speed 較高不能直接等同於最終絕對搜尋成本較低。

**逐題節點數、秒數與成本。** [body.py:73](/home/lorkhan/repo/arcagi/src/arcagi/hammer/body.py:73) 摘錄欄位：`nodes、nodes_to_first、near_score、seconds`；目前 [quick.py:148](/home/lorkhan/repo/arcagi/src/arcagi/treegen/quick.py:148) 的 `per_task` 只收 `solved／auc／nodes_to_first`，秒數仍在 `epochs/<n>/solutions.jsonl`。

例如 [親代 epochs/4/solutions.jsonl:9](/home/lorkhan/code/playground-arc1/ws/evo/pop/g0/parent/quick/root/epochs/4/solutions.jsonl:9) 摘錄：`nodes_to_first:1338, seconds:0.073`；[子代 1 同檔:9](/home/lorkhan/code/playground-arc1/ws/evo/pop/g1/1_bb25cbafd96e/quick/root/epochs/4/solutions.jsonl:9) 為 `1336, 0.062`。

相關性：逐題秒數已存在，但目前沒有獨立命名的 `seconds_to_first`；這兩筆秒數差異也未做重跑雜訊驗證。

[seed_enum.cpp:629](/home/lorkhan/repo/arcagi/native/src/seed_enum.cpp:629) 在搜尋輸出符合訓練目標時設定 `nodes_to_first`；[body.py:68](/home/lorkhan/repo/arcagi/src/arcagi/hammer/body.py:68) 之後另驗 `train_ok／test_ok`。`cost` 則是各 epoch 的 body／shadow／meta／foundry evals 加總，包含 epoch 0，見 [think1_meter.py:65](/home/lorkhan/repo/arcagi/scripts/think1_meter.py:65)。

相關性：首解節點應連同 test_ok 讀取；它不是保證泛化正確的首解，也不是牆鐘成本。

**目前未解與邊緣題。** [H/epochs/8/solutions.jsonl:1](/home/lorkhan/code/playground-arc1/ws/hammer/epochs/8/solutions.jsonl:1) 的前 16 列是 L16；最新完成 epoch 8 解出 6 題，未解 10 題：

`a740d043、95990924、c0f76784、6f8cd79b、22233c11、af902bf9、ba97ae07、e76a88a6、995c5fa3、1b60fb0c`。

可直接定位的邊緣紀錄：

- [H/epochs/0/solutions.jsonl:5](/home/lorkhan/code/playground-arc1/ws/hammer/epochs/0/solutions.jsonl:5)：`1e0a9b12`，首解 `24739`，接近 C25 的 25,000。
- [H/epochs/8/solutions.jsonl:7](/home/lorkhan/code/playground-arc1/ws/hammer/epochs/8/solutions.jsonl:7)：`ce4f8723`，首解 `20839`。
- [H/epochs/8/solutions.jsonl:12](/home/lorkhan/code/playground-arc1/ws/hammer/epochs/8/solutions.jsonl:12)：`beb8660c`，`test_ok:true`、首解 `76003`、`gate_ok:false`；此題在 C25 的親代／子代紀錄均未解。

相關性：已有跨越 25k／100k 預算區間的具體題目，但活樹與淨態快撥的庫／狀態不同，不能只把差異歸因於預算。

**其他池與成績路徑。** [H/README.md:48](/home/lorkhan/code/playground-arc1/ws/hammer/README.md:48) 指出 `truth/train/taskset.json` 放 L16／P48，`truth/cal/ids.json` 放 H8／H24；逐輪成績在 `epochs/<n>/{curve.csv,solutions.jsonl,status.json}`。依 epoch 8 的逐題列加總：

| 池 | 題數 | train_ok | test_ok |
|---|---:|---:|---:|
| L16 | 16 | 6 | 6 |
| P | 48 | 15 | 15 |
| H8 | 8 | 1 | 0 |
| H24 | 24 | 3 | 2 |

相關性：其他池有未解與訓練擬合後測試失敗的題目；快撥預設清 P，但仍跑 H8／H24。

## 3. 「故意改笨」可動欄位與 check 限制

**目前沒有已驗證「改了必然降分」的欄位。** [genome.py:91](/home/lorkhan/repo/arcagi/src/arcagi/treegen/genome.py:91) 摘錄：`Allow only the four mutation surfaces and op deletion/recombination`。可動面包括 op status、刪除 op、gate 數字、route priority、judge 數字、節點 weight；但第 1 題已見刪 route／改 weight 可保持相同搜尋成績。

相關性：程式允許修改某欄位，不等於已建立它與降智的必然關係。

| 手段 | 來源短摘錄與 check 行為 |
|---|---|
| 刪算子 | [genome.py:95](/home/lorkhan/repo/arcagi/src/arcagi/treegen/genome.py:95) 逐一檢查留下的 op，允許刪除；但原有 gate 必須 live、至少留一個 decomp；[check.py:68](/home/lorkhan/repo/arcagi/src/arcagi/treegen/check.py:68) 另要求至少一個 live comb／gate。 |
| 全 dormant | 同上會觸發 `gate_not_live`、`missing_live_comb`、`missing_live_gate`，不能通過 GA check。 |
| 砍預算 | [genome.py:118](/home/lorkhan/repo/arcagi/src/arcagi/treegen/genome.py:118) 的骨架比較沒有排除 budgets，故相對親代改預算會報 immutable；且 [quick.py:98](/home/lorkhan/repo/arcagi/src/arcagi/treegen/quick.py:98) 會再次用外部 L／epochs 覆寫。 |
| judge 門檻 | [bounds.json:4](/home/lorkhan/repo/arcagi/reports/think2-1109/ga/bounds.json:4) 允許 `new_solves_min:0..16`、`drop_min:0..8`、`se_mult:0..6`、`ntf_ratio_max:0.25..8` 等有限範圍。 |
| 節點 weight | [bounds.json:19](/home/lorkhan/repo/arcagi/reports/think2-1109/ga/bounds.json:19) 範圍為 `0.25..4.0`，不能設 0 通過 bounds。 |

相關性：以上是現有合法變異面與結構下限，沒有附帶效能退化保證。

**部分 judge 欄位沒有接到快撥判斷。** [epoch.py:346](/home/lorkhan/repo/arcagi/src/arcagi/hammer/epoch.py:346) 確實讀 `frozen["judge"]["no_crowd"]["ntf_ratio_max"]`；[epoch.py:300](/home/lorkhan/repo/arcagi/src/arcagi/hammer/epoch.py:300) 讀 `ablate_max`。但 [judge.py:41](/home/lorkhan/repo/arcagi/src/arcagi/hammer/judge.py:41) 摘錄：`hit = bool(ev["new_solves"]) or ev["witness_hits"] > 0`，函式沒有接收 frozen stage1／stage2 參數。

相關性：把 `stage1.new_solves_min` 調高，依目前這條程式路徑，不能宣稱一定提高實際晉升門檻。

**check 擋什麼。** [check.py:55](/home/lorkhan/repo/arcagi/src/arcagi/treegen/check.py:55) 到 :91 依序檢查 schema、重算 sha、引用可解與 unused defs、immutable、數字範圍、live comb／gate、匯入後格式，以及新增洩漏；繼承的污染只列診斷。它沒有跑解題效能驗證。

相關性：check 是合法性檢查，不會要求變體保有原親代解題能力。

**另有檢查較少的入口。** [quick.py:89](/home/lorkhan/repo/arcagi/src/arcagi/treegen/quick.py:89) 可直接複製來源目錄；:107 呼叫的是 `hammer.check_root`，沒有呼叫 `treegen.check`。[hammer/check.py:35](/home/lorkhan/repo/arcagi/src/arcagi/hammer/check.py:35) 與 [formats.py:193](/home/lorkhan/repo/arcagi/src/arcagi/hammer/formats.py:193) 檢查檔案、列欄位與 enum，沒有 GA 的 live 數量及親代 immutable 比較。

相關性：從程式可確認 quick 直接入口與 GA 入口的檢查強度不同；本次沒有建立或執行任何繞過變體。

## 4. crossover、mutate、D27 與 D18 接線現況

**crossover 沒有拒絕同 sha。** [crossover.py:66](/home/lorkhan/repo/arcagi/src/arcagi/treegen/crossover.py:66) 摘錄：`return genome.pack(a_doc, a), {... "redraws": 0}`，打包後直接回傳，沒有比較子代與親代 sha。[ga.py:197](/home/lorkhan/repo/arcagi/src/arcagi/treegen/ga.py:197) 的 duplicate 檢查只在 `index < 5` 的突變分支；交配分支 :200～209 沒有此檢查。

相關性：交配塌成親代複本目前會被接受。

實際紀錄：

- [E/pop/g1/5_4575d1c8c153/parents.json:13](/home/lorkhan/code/playground-arc1/ws/evo/pop/g1/5_4575d1c8c153/parents.json:13)：X1 的親代之一就是 `4575d1c8c153`，與子代 sha 相同。
- [E/pop/g1/6_095e8f1b0f99/parents.json:41](/home/lorkhan/code/playground-arc1/ws/evo/pop/g1/6_095e8f1b0f99/parents.json:41)：X3 的親代之一就是 `095e8f1b0f99`；[fit.json:3](/home/lorkhan/code/playground-arc1/ws/evo/pop/g1/6_095e8f1b0f99/fit.json:3) 記 `cache_hit:true`，:388 記 `quick_ran:false`。

**mutate 的拒重在 GA 外層。** [mutate.py:123](/home/lorkhan/repo/arcagi/src/arcagi/treegen/mutate.py:123) 把數字裁進範圍後直接 pack，沒有自行拒絕原值／同 sha。[ga.py:188](/home/lorkhan/repo/arcagi/src/arcagi/treegen/ga.py:188) 初始化 `seen={parent_sha}`；:197～199 遇 seen 就記 `duplicate_mutation` 並重抽，:235 加入接受的突變 sha；最多 20 draws。

相關性：直接呼叫 mutate 與透過 ga.run，拒重保障不同。

**D27 活動量版在 fitness.py。** [fitness.py:16](/home/lorkhan/repo/arcagi/src/arcagi/treegen/fitness.py:16) 摘錄：`weights = {name: 1 + len(live[name]) + events[(epoch, name)] ...}`；事件歸屬為 `incubate→grow`，`promote/demote/retire→judge`。[fitness.py:153](/home/lorkhan/repo/arcagi/src/arcagi/treegen/fitness.py:153) 的 cache miss 評分會直接呼叫它。

相比之下，[credit.py:156](/home/lorkhan/repo/arcagi/src/arcagi/treegen/credit.py:156) 的 `build()` 仍用 active 節點的 metainfo weight；[ledger.py:59](/home/lorkhan/repo/arcagi/src/arcagi/treegen/ledger.py:59) 仍接這個版本。沒有找到 `--activity` 或同類切換旗標。

相關性：D27 已接入 GA 評分，但塊 3 ledger 的預設分配仍是靜態 weight；這是兩條入口，不是一個預設關閉的 CLI 開關。

實跑證據：[子代 1 quick/credit.json:4](/home/lorkhan/code/playground-arc1/ws/evo/pop/g1/1_bb25cbafd96e/quick/credit.json:4) 摘錄 epoch 1 活動量 `grow:1、judge:1、route:7、solve:5`；epoch 2 的 judge 變成 2。

**D18 已接線且跑過引導臂。** [ga.py:171](/home/lorkhan/repo/arcagi/src/arcagi/treegen/ga.py:171) 載入 guide；[mutate.py:99](/home/lorkhan/repo/arcagi/src/arcagi/treegen/mutate.py:99) 摘錄：`arm = "guided" if rng.random() < 0.8 else "uniform"`；[mutate.py:75](/home/lorkhan/repo/arcagi/src/arcagi/treegen/mutate.py:75) 實作 stale 刪除 ×4、部分 status／credit 目標 ×2。實際五個突變的 arm 是：

`uniform、guided、guided、uniform、guided`。

其中 [子代 1 parents.json:2](/home/lorkhan/code/playground-arc1/ws/evo/pop/g1/1_bb25cbafd96e/parents.json:2) 明記 `guided`，把 `comb_g1_cd450dff4b` 改 dormant。

相關性：可以確認接線與執行，尚不能從這五個樣本判定引導臂有效。

另有一處接線限制：[health.py:54](/home/lorkhan/repo/arcagi/src/arcagi/treegen/health.py:54) 只輸出 `retire-candidate／dormant-stale` 建議，而 mutate 有 `dormant-active` 加權分支。

相關性：正常 health 輸出的 guide 不會提供 dormant-active 那條加權提示。

## 5. 快撥並行、耗時與 GPU 評估器

**threads 的用途。** [quick.py:185](/home/lorkhan/repo/arcagi/src/arcagi/treegen/quick.py:185) 傳 threads 給 epoch；[body.py:103](/home/lorkhan/repo/arcagi/src/arcagi/hammer/body.py:103) 再變成 `arcbatch --threads N`。[seed_main.cpp:119](/home/lorkhan/repo/arcagi/native/src/seed_main.cpp:119) 摘錄：建立 N 個 `std::thread`，用 atomic 索引分派工作。

相關性：threads 並行的是底層題目搜尋；quick 本身沒有同時評估多個樹個體。

**多程序副本的路徑隔離。** [body.py:129](/home/lorkhan/repo/arcagi/src/arcagi/hammer/body.py:129) 用 `TemporaryDirectory(dir=root/tmp)`，body 暫存有唯一目錄。但 [quick.py:104](/home/lorkhan/repo/arcagi/src/arcagi/treegen/quick.py:104) 寫 `root.parent/quarantine_P.json`，[quick.py:226](/home/lorkhan/repo/arcagi/src/arcagi/treegen/quick.py:226) 寫 `root.parent/quick.json`。

相關性：靜態看可以用多程序跑不同副本，但每份須連父目錄一起隔離；同一父目錄下僅用不同 root 名稱，輸出仍會衝突。本次未做並行實跑。

**C25≈15 秒、C50≈35 秒的原始出處。** [b2/accept.json:4](/home/lorkhan/repo/arcagi/reports/think2-1109/b2/accept.json:4) 摘錄：

- C25：`wall_s:[15.52,15.18,14.18]`。
- C50：`L:50000, epochs:6, wall_s:[33.11,37.27,38.15]`。
- 註記：當時系統 load 8～11。

[03b 設計:100](/home/lorkhan/repo/arcagi/notes/rounds/gpu-night-1109/think-2/03b-設計-塊2.md:100) 定義 C25＝25k／4、C50＝50k／6；兩者含 epoch 0，實際分別執行 5／7 個 epoch。

相關性：15／35 秒有既有量測支持，但不是目前負載下重新量到的保證。

**本機可見的 GPU 工具。** 已唯讀確認下列 binary 均存在且有執行權限，未啟動 GPU 工作：

| 工具 | 來源、短摘錄與評估單位 |
|---|---|
| `gpusearch` | [gpu.hpp:11](/home/lorkhan/repo/arcagi/native/gpu/gpu.hpp:11)：載入單題 `DTask`、inputs、targets、`DStep` 字母表；`gpu_run(depth,start,count,...)` 評估程式索引區間。 |
| `gpgp／gpgp-ho` | [gp.hpp:7](/home/lorkhan/repo/arcagi/native/gpu/gp/gp.hpp:7)：`GP_LMAX=10`；[report.md:12](/home/lorkhan/repo/arcagi/reports/gpu-gp-1109/report.md:12) 的個體是字母表索引序列；[holdout.md:7](/home/lorkhan/repo/arcagi/reports/gpu-gp-1109/holdout.md:7) 有 holdout／MDL／simplify 旗標。 |
| `gpuprofile` | [progress.md:6](/home/lorkhan/repo/arcagi/reports/task-features-1109/progress.md:6)：GPU near-miss 剖面；抽查 perfect 數與 gpusearch 一致。 |
| `gpuseed` | [progress.md:5](/home/lorkhan/repo/arcagi/reports/seed-gpu-1110/progress.md:5)：一階 seed 原語的一層評估；100 題、2～6 層指紋集合與節點數和 CPU 一致。 |
| `arcbatch-gpuseed` | [e2e.hpp:35](/home/lorkhan/repo/arcagi/native/gpu/seed/e2e.hpp:35)：`e2e_run_chunk` 評估列舉器候選片段；[report.md:11](/home/lorkhan/repo/arcagi/reports/seed-gpu-e2e-1110/report.md:11) 說明 `--gpu-seed` 接入真實 seed 搜尋。 |
| `gpusynth／gpusynth_verify` | [gpusynth.cu:1](/home/lorkhan/repo/arcagi/native/gpu/synth/gpusynth.cu:1)：E11 v2，28 個一階原語，隨機 postfix 程式，輸出 `(task,ex,prog,out)`；verify 用 CPU seed 解譯器重驗。 |

相關性：已有格子步驟、seed 列舉片段與逆向合成三類 GPU 能力，輸入介面各不相同。

**gpusynth v2 與 git log。** `git log -- native/gpu` 可見：

- `27bec54`：`E11 gpusynth v2: CPU-verified semantics ...`
- `d6b738d`：`gpuseed-e2e ... inside real seed search`
- `3f73ec6`：`gpuseed ... one seed Enumerator layer`
- `55e907f`：`gpuprofile ... near-miss profiler`

[gpusynth/report.md:25](/home/lorkhan/repo/arcagi/reports/gpusynth-1110/report.md:25) 的既有驗證合計約 45k 列、0 mismatch；:35 明列 **and／or 沒有樣本覆蓋**；:42 的 30 秒相異率為 31.2%。

相關性：v2 有 seed 語意驗證資料，但不是完整 AST／整棵樹語意覆蓋。

**整棵樹介面。** [think-2/01-簡報.md:57](/home/lorkhan/repo/arcagi/notes/rounds/gpu-night-1109/think-2/01-簡報.md:57) 摘錄：「兩者都沒有評估『整棵 hammer 樹變體』的介面」。現有 quick 仍固定呼叫 native CPU body；`arcbatch-gpuseed` 是另一支 binary，未被 [body.py:32](/home/lorkhan/repo/arcagi/src/arcagi/hammer/body.py:32) 指定。

相關性：後來新增的 seed GPU 層仍不等於完整 hammer 個體評估介面；既有端到端報告還顯示 1e6 時 GPU 21.1 秒、CPU 9.1 秒，見 [e2e/report.md:22](/home/lorkhan/repo/arcagi/reports/seed-gpu-e2e-1110/report.md:22)。

## 6. 塊 5 Janet 與 node-pool

**Janet 專案慣例。** [J/conventions.md:11](/home/lorkhan/repo/langs/janet-lab/wf/workflows/common/conventions.md:11) 摘錄：

- 檔案 ≤150 行且 ≤8192 bytes。
- 模組一資料夾，`init.janet` 只 re-export。
- kebab-case；謂詞尾 `?`、修改狀態函式尾 `!`。
- 註解繁中。

相關性：這些是 janet-lab 現有程式組織與命名慣例。

**S 式表示。** [J/docs/01:3](/home/lorkhan/repo/langs/janet-lab/docs/01-語言速成.md:3) 摘錄：`(函式 參數...)`；:15～28 區分 tuple／array、struct／table，以及 `@` 可變版本。[J/docs/08:3](/home/lorkhan/repo/langs/janet-lab/docs/08-巨集-macro.md:3) 摘錄：「程式就是資料（tuple / array）」、「吃 AST、吐 AST」。

相關性：Janet 已有原生巢狀程式資料表示；但本次未找到 hammer tree 的 Janet 序列化契約。

**讀寫與解析。** [J/reference/巨集工具與求值.md:94](/home/lorkhan/repo/langs/janet-lab/reference/巨集工具與求值.md:94) 摘錄：`parse` 只回第一個值；`parse-all` 回裝全部值的 array。[J/docs/18b:14](/home/lorkhan/repo/langs/janet-lab/docs/18b-格式化與印出.md:14) 區分 `%q` 可能截斷、`%n` 不截斷，並註明 `%j` 是 Janet 表示法、**不是 JSON**。[J/docs/19:9](/home/lorkhan/repo/langs/janet-lab/docs/19-檔案與檔案系統.md:9) 摘錄：`spit` 寫入、`:ab` 附加、`slurp` 回 buffer。

相關性：已有文字表示、解析與檔案 I/O 可查；不能把一般 pretty print 或 `%j` 當成 JSON 往返保證。

JSON 橋接另見 [J/docs/03:64](/home/lorkhan/repo/langs/janet-lab/docs/03-json.md:64)：`json/decode` 的第二參數控制 keyword keys，第三參數控制 null→nil；:85 提醒 table 無法存 nil，開啟後該鍵會消失。

相關性：tree／quick 裡含大量 null，JSON→Janet 的空值選項會影響資料保留方式。

**指定 aos Janet 目錄不存在。** 唯讀查詢回覆：

`/home/lorkhan/repo/simple_tools/aos/extras/langs/janet: No such file or directory`

連父目錄 `extras/langs` 也不存在。

相關性：本次無法從該路徑取得 aos 的 Janet 慣例或工具。

**node-pool 要點。** [N/README.md:34](/home/lorkhan/repo/simple_tools/aos/proto8/thinking/2026-11/08/node-pool/README.md:34) 摘錄：節點是含 `_metainfo.json` 的定義資料夾；梯度是一行 `_gradients.jsonl`；改進鏈最多 2 層。[N/03-設計.md:42](/home/lorkhan/repo/simple_tools/aos/proto8/thinking/2026-11/08/node-pool/03-設計.md:42) 定義錢為可改公式的抽象分數，起步為千 token＋秒／10；:60～64 定義：

接受任務數產生預算 → 每層先報銷 → 利潤留 20%、其餘分紅 → 扣房租 → 連續零餘額列退休建議。

相關性：這份來源強調成本歸屬、分配守恆與退休建議，沒有把零餘額直接當成刪除命令。

[N/03-設計.md:20](/home/lorkhan/repo/simple_tools/aos/proto8/thinking/2026-11/08/node-pool/03-設計.md:20) 還記錄舊公式會先餓死真正花 token 的 kb_link，0 token 腳本反而累積餘額。

相關性：節點池已有「分配公式可能反向獎懲」的具體試算紀錄。

**本機執行檔。** `command -v janet` 回傳：

`/home/lorkhan/.local/bin/janet`

相關性：PATH 中可找到 Janet；本次未啟動它，也未重驗版本。

## 7. noise.py／compare 在 σ＝0 時的「顯著」

**成對 bootstrap 算法。** [noise.py:21](/home/lorkhan/repo/arcagi/src/arcagi/treegen/noise.py:21) 摘錄：

`d_t = b.per_task[t].auc - a.per_task[t].auc`

取兩邊共同題號，有放回抽同樣題數、加總差值，重複 n_boot 次；以樣本的 `statistics.pstdev` 當 sigma。全部 `d_t=0` 時不抽樣，直接 `sigma=0.0、degenerate=true`。

相關性：這量的是題目重抽樣的不確定性，不是搜尋執行時間的雜訊。

**目前 GA 的 σ＝0 規則：不宣稱顯著。** [noise.py:87](/home/lorkhan/repo/arcagi/src/arcagi/treegen/noise.py:87) 摘錄：`"z": delta / sigma if sigma else None`。[fitness.py:54](/home/lorkhan/repo/arcagi/src/arcagi/treegen/fitness.py:54) 摘錄：`"significant": z is not None and abs(z) >= 2`。

所以 σ＝0 時，`z=null`，GA 的 `significant=false`。這也包含「每題差值都相同且非零」造成零標準差的情況；此時 `degenerate` 仍可能是 false，因為該旗標只檢查所有差值是否為零。

相關性：零 sigma 沒有被轉成無限大 z，也不會在 GA 自動視為顯著。

實際證據：[子代 1 fit.json:125](/home/lorkhan/code/playground-arc1/ws/evo/pop/g1/1_bb25cbafd96e/fit.json:125)：

`d_auc_L:0, degenerate:true, sigma:0.0, significant:false, z:null`。

**舊 compare 有不同規則。** [scripts/think1_meter.py:109](/home/lorkhan/repo/arcagi/scripts/think1_meter.py:109) 摘錄：

`significant = abs(d_auc_L) > 2 * sigma`

因此這支舊工具在 σ＝0 且 Δ≠0 時會回 true；Δ＝0 回 false；缺 noise.json 時顯著性是未知。

相關性：專案內「compare」有兩套零 sigma 行為；目前 treegen GA 使用前述 `noise.compare → fitness.comparison`。

## 缺口／未知

- **降智保證**：未找到已實跑、保證比親代差且通過 GA check 的負對照；刪 op、休眠與改門檻目前只有可動性證據。
- **量尺穩定性**：節點數／成本已見差異；逐題秒數尚未做重跑雜訊驗證，也沒有獨立的首解秒數欄位。
- **預算因果**：活樹與淨態快撥的庫、狀態、P 池不同，不能由既有紀錄單獨判定某題只差預算。
- **演化效果**：D18／D27 已接線並產生實際輸出，尚無足量對照證明引導優於均勻突變；交配拒重仍缺。
- **並行實證**：多副本並行只做路徑與程式檢查，沒有啟動並行快撥。
- **GPU 範圍**：未找到整棵 hammer genome 的 GPU 評估 API；gpusynth 的 and／or 仍缺實測覆蓋。
- **Janet 接點**：指定 aos Janet 目錄不存在；未找到 hammer tree 的 Janet 往返格式、雜湊或執行契約。
- **顯著性一致性**：舊 meter compare 與目前 GA 在 σ＝0、Δ≠0 時規則不同；本次只記錄現況，未改規則。