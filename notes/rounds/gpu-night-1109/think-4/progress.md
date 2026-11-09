# think-4 progress（先修量尺再演化）

主題：①修快撥量尺（C25 auc_L 全 20）②演化缺口（交配同 sha、D27、D18）③塊 5 Janet＋節點池。流程見 `../思考輪-流程.md`。

## 第一棒（t4 隊長）

- [完] 01a 蒐集（codex sol 唯讀，`arcagi-t4-gather`，26 KB）。
- [完] 01-簡報：隊長親查 auc_L=20 根因＝**5 題從 e0 就由庫存積木命中、11 題 25k 內永不解，5×4=20**；尺量的是庫存不是學習。另更正：D27、D18 已接線，缺的是對照證據。
- [完] 02 fable（10 KB）：剝庫量學習、主分 learn_bits、題集 L′、6 棵改笨樹、顯著門 |z|≥2＋兩半同號、meter.py/dumb.py/cli。
- [完] 02b Argon（18 KB，無 auth 錯）。至少兩條 P0：①learn_bits 不扣 e0、e0 靜態解題重複領 4 次分→主體仍量靜態搜速非跨輪學習；②L′ 取 P48 最易 10 題→剝庫後要嘛免學即解、要嘛全掛。
- [完] 代定清單 T1–T7（照 fable 推薦）。

## 下一步（第二棒）

1. 讀 `02b-Argon審.md` 全文（18 KB，用 grep／分段），逐條在 `代定清單.md` 標「維持／改」——P0 ①② 必回應（T2 主分可能改「扣 e0 的跨輪增量＋e0 靜態分分列」；T4 選題改邊緣題梯度）。
2. 寫 `03-設計.md`（塊 A 量尺：meter.py／dumb.py／quick.py 改點／cli meter、dumb、meter-batch、meter-accept；驗收寫死含「≥3 改笨樹顯著、judge-high 不顯著、≥1 個 g1 子代顯著」）。
3. 施工交 codex sol（`-m gpt-6.1-sol -s workspace-write -C /home/lorkhan/repo/arcagi --add-dir /home/lorkhan/code/playground-arc1/ws/evo`），任務書帶本夾安全邊界；隊長審 diff→實跑（systemd-run arcagi-t4-<名>，worker ≤4）→ commit → `04-總結簡報.md`。

## 第二棒（t4b，11-10）

- [完] 代定重議：`代定清單.md` 末「第二棒重議」表（T2 gain_bits 扣 e0、train-only、B_ref 固定；T4 校準分層選題；T5 閉式 σ＋|Δ|≥2；T7 run 目錄唯一後綴）。
- [完] `03-設計.md`（計分、選題、顯著門、5 笨樹、檔案、驗收 5 條）。
- [進行] codex sol 施工：單元 `arcagi-t4b-codex`，任務書／log／回報在 scratchpad `t4b/`（brief.md、codex.log、codex-last.md）。完成判斷：codex-last.md 存在。之後隊長審 diff → 跑 `t4b/pipeline.sh`（包 `arcagi-t4b-pipe`）→ `reports/think4-1110/a/accept.json`。
- [完] codex 施工（commit 20d95f6）：meter.py／meter_{stats,cli,suite,fake}.py／dumb.py／test_meter.py；123 tests 綠。原三笨樹配方查證無效（lib_cap、gate dormant、judge 門檻都沒被讀），改為副本內 pause grow/foundry/judge（見 dumb.py docstring、`04-施工紀錄.md`）。
- [完] 實跑 pipeline（20 題 L′、C50/4、jobs 4）→ `reports/think4-1110/a/accept.json`：**FAIL（只差 (a)）**。
  - (a) no-learn／gate-dormant／judge-block 對親代 gain_bits：Δ=−90.0 bits、兩半同號負，但 σ=55.3、**z=−1.63 <2** → 不顯著。base_bits Δ=0（剝學習不動 e0，對）。
  - 逐題：只 4 題大掉（62c24649、67e8384a 從解變不解；6d0aefbc、c9e6f938 12.6→4.3），其餘多題 no-learn 反小升 0.2–3.6 bit → σ 被拉大。gain 只在 e0→e1 發生、e1..e4 全平（E=4 等於把一步乘 4）；no-learn 仍有 gain 73 bits（e0→e1 有非 comb 的改善）。
  - (b) 親代兩次 Δ=0、σ=0、不顯著；null 不顯著 ✔。(c) 三種假件全被拒 ✔（per_task 竄改、same_sha、test_as_train）。門：raw verify 全 PASS、identity 全對。
  - no-decomp 對 base／gain 都 Δ=0（decomp 第 2 個在此題集無作用）。
  - 校準：64 題中 learned+sped=12，但 20 題子集只剩 4 題轉移（踏腳石被切掉，Argon P0-2 應驗）。
- [進行] 翻案跑 full-64（全 64 題當 L′，親代×2＋5 笨樹）：單元 `arcagi-t4b-full64`（scope），腳本 `/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/t4b/full64/run.sh`，輸出 `/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/t4b/full64/{batch.json,accept.json,batch.log,accept.log}`；跑完判斷＝`/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/t4b/full64/DONE` 存在。
  - 判讀：`python3 -c "import json;a=json.load(open('/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/t4b/full64/accept.json'));print(a['status']);[print(k,v['gain_bits']['delta'],v['gain_bits']['z'],v['gain_bits']['halves_same_sign']) for k,v in a['comparisons'].items()]"`
  - 若 no-learn 類 z≤−2 → 題集改 full-64（T4 再改），accept.json 複製進 reports/think4-1110/a/full64/；若仍 <2 → 翻案點：主分改「相對 no-learn 對照的 gain」或成對符號檢定（需先寫進 03 再跑，避免事後調門）；並查 e0→e1 非 comb 改善來源。
- 未做：04-總結簡報、g1 子代量測。reports 下 pytest-* 暫存夾不 commit。
- [完] full-64 翻案跑結果（`t4b/full64/summary.txt`）：**仍 FAIL**。no-learn／gate-dormant／judge-block Δgain=−88.2、兩半同號負、z=−1.51（比 20 題更差，加題只加 σ）；親代自比、null Δ=0；raw verify 全 PASS。結論：擴題集救不了，下一棒走翻案點二（主分改「相對 no-learn 的 gain」或成對符號檢定，先寫進 03 再跑），並查 e0→e1 非 comb 改善來源。

## 第三棒（t4c，11-10）

- [完] 73 bits 來源 → `05-增益來源.md`：**非量尺 bug**；no-learn 漏關 hammer 的「uses→列舉順序」管道（epoch.py:317-321 累加 uses 不受 pause 控制、:250 order_from_uses）。逐題：e0/e1 程式相同、只 ntf 變小（transpose 35→12 等 17 題）。舊 Δ≈−88 只是 comb 管道貢獻；親代 173 ≈ 順序 85＋comb 88。
- [完] 預先登記 03 §8（commit **f1991f8**，早於重跑）：對照改 `no-learn-all`（清 uses）、主判準＝單尾成對符號檢定 p≤0.05＋Δ≤−2＋兩半負；健全門 no-learn-all |gain|<1；新種子＝預算擾動 L=40000（hammer 決定論無種子）。
- [完] codex 施工 commit **1629ce3**（dumb no-learn-all、meter 清 uses、sign_test、--labels、--criterion t4c；158 tests 綠）。src/arcagi/solvers/gated.py 與 tests/solvers/test_gated_gpu_fallback.py 的改動**非本線**，未 commit。
- [完] 重跑 **PASS**（見下行判讀；accept/batch 複本在 `reports/think4-1110/c/`）：親代 vs no-learn-all 18/18 負、p=3.8e-6、Δ=−168.7、兩半 −52.6／−116.1；no-learn-all gain=0；null Δ=0；fake／raw_verify／repeat 全過。原單元 `arcagi-t4c-run`（scope），腳本 `/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/t4c/run.sh`；輸出 `/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/t4c/{batch.json,batch.log,accept.json,accept.log}`；跑完判斷＝`/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/t4c/DONE` 存在。
  - 判讀：`python3 -c "import json;a=json.load(open('/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/t4c/accept.json'));print(a['status'],a['checks']);[print(k,v['n'],v['k'],v['n_pos'],v['p_neg'],v['delta'],v['halves']) for k,v in a['sign_tests'].items()];print(json.dumps(a['report_only'])[:800])"`
  - 過 → accept.json 複製進 `reports/think4-1110/a/t4c/`、更新代定清單 T2/T5、寫 04-總結簡報。
  - 不過 → **不再翻案**：代定清單加「待使用者裁」條目（附預設：維持 t4c 判準記 FAIL，量尺僅作回報用、不當 GA 適應度；或改用 comb 管道與順序管道分列回報），附 accept.json 數字。

## 第四棒（t4d，11-10）

- [完] t4c 收尾（commit 58e27ce）：accept/batch/taskset 複本 `reports/think4-1110/c/`；05、代定清單（T2/T4/T5 定案、T8 新）標結論；`04-總結簡報.md`。
- [完] 03 §9 g1 子代量測預先登記（commit **7d987f9**，早於跑）：5 棵相異子代（c0..c4）、雙尾成對符號檢定、Holm m=5、|Δ|≥2、兩半同號；親代重跑 parent-g＋clone（c7）陰性對照；健全門三條。
- [進行] g1 量測：單元 `arcagi-t4d-g1`（scope），腳本 `/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/t4d/run.sh`（7 棵 meter，xargs -P 4，每棵約 3.5 分鐘，總計約 8–10 分鐘）；逐棵 log `/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/t4d/logs/`、回傳碼 `/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/t4d/rc.txt`；run 目錄 `ws/evo/meter/t4d-*`。跑完判斷＝`/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/t4d/DONE` 存在。
  - 判讀：DONE 後 run.sh 已自動跑 `/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/t4d/g1_judge.py` → `reports/think4-1110/d/g1.json`，摘要在 `/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/t4d/judge.log`（首行 PASS/FAIL＋健全門，之後每行：族 子代 n k_neg k_pos p Δ 兩半 holm_reject verdict）。judge 掛了就手動重跑：`.venv/bin/python -I /tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/t4d/g1_judge.py`。
  - 下一步：g1.json commit；結果寫進 04-總結簡報「下一步」與 progress；預期 c1、c2（只改 comb 狀態）Δ=0（strip=all 盲區）。健全門不過＝量測無效，不解讀。

## 第五棒（t4e，11-10）

- [完] g1 結果：有效、c0..c4 每題 Δ=0（`reports/think4-1110/d/g1.json`）。
- [完] 查因 → `06-g1全零.md`：c0 節點 weight hammer 不讀（死欄位）；c1/c2 comb 狀態被 strip=all 剝（量尺盲點，同 T8）；c3/c4 刪/休眠 `route_starve_rt_sleep` 被 rt_pool(priority 2) 遮蔽且 starve 從未出現（gate_in 14–20）。quick cost 旁證：c0/c3/c4 與親代同為 7294813。elites c3/c4 是中性漂移。
- 待裁 T9–T12 已列代定清單（附預設）。未修 GA、未改 hammer。
