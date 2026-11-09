## Q1 r09 收尾狀態

- **來源**：
  - A：[ /home/lorkhan/repo/arcagi/notes/rounds/r09/04-總結簡報.md ](/home/lorkhan/repo/arcagi/notes/rounds/r09/04-總結簡報.md)
  - B：[ /home/lorkhan/repo/arcagi/notes/rounds/r09/05-白話進度.md ](/home/lorkhan/repo/arcagi/notes/rounds/r09/05-白話進度.md)
- **摘錄**：

  A，判準與 r10 待辦；以下為原文節錄，省略處以「…」表示：

  > M0：「過：arcbatch 跑 `dec-g1`，sha `7aebb3c73f28`」；M1：「H24 逐 epoch 不退…熔斷 0 次）、false_pos 0、llm_calls 0、purity 過」。
  > M2(a)：「過：`comb_g1_2ff25d9c21`…`by:sleep`…新解 P 題 62c24649、67e8384a；同一批升級帶來 H24 +1」。
  > M2(b)：「字面過、打折」；折外 0 掉題、多解 6 題、節點降 32.8%；「多解來自 r08 手寫 halves／nest，結果只寫在暫存樹，活樹沒套用」。
  > M2(c)：「不過：真蠟模 b27ca6d3 三段都沒擬合到」；M2(d)：「不過：AUC_L 40 < hammer-static 48；H8 0→0」。
  > M3：「大致準」；M4：「已排除：沒有 `add-op --live`；lib_bits 的升降不計」；M5：「無…全 dormant 時 AUC_L＝32…回滾 0 次」。
  > r10：「鑄模請求附上空樹的 32 個原語」；先用「S2 19 題預核 fit_rate」；「斷裂面要累積，交給縱拆」。
  > r10：「插 §5.1 的補丁 M1～M7」；「把 halves／nest 搬到 C++（另加 `forbid`）」；「`rt_gatescan` 臂直接呼叫 `scan --write`」。
  > r10：「鍛造爐（金髮女孩、對手抽樣）照 v3／v4 開工」；「aos-self-opt 第二輪…從 `src/arcagi/hammer/` 抽 `formats`、`ops`、`stall`、`route`」。

  B：

  > 「8 個 epoch 要 5 分鐘，超過目標，因為手寫的 halves 拆法升上去之後只能走 Python」。
  > 「LLM 解 b27ca6d3 時切成三步：大小 2 的物件塗 8、在 8 外圈畫 3、8 改回 2。空樹只有 32 個 list 原語…200k 預算內一段都擬合不到」。
  > 「手寫的 halves 只有 Python 版，一上線整棵樹就慢 8 倍」。
  > 「門的參數在現在的引擎裡多半沒作用，拿掉原語在折外都會掉題」。
  > AUC_L：主樹 40、不學對照 32、手寫拆法對照 48；H24：1→2；H8：全 0。

- **相關性**：這些紀錄界定了 aos 樹自我改進已有的證據、尚未成立的證據，以及語言可表達性與執行成本兩個實際卡點。

## Q2 v4 M1～M7 待插項目

- **來源**：
  - A：[ /home/lorkhan/repo/simple_tools/aos/proto8/thinking/2026-11/08/alt-fable/out2/v4-Argon整合.md ](/home/lorkhan/repo/simple_tools/aos/proto8/thinking/2026-11/08/alt-fable/out2/v4-Argon整合.md)，§5.1。
  - B：[ /home/lorkhan/repo/arcagi/notes/rounds/r09/04-總結簡報.md ](/home/lorkhan/repo/arcagi/notes/rounds/r09/04-總結簡報.md)，§2、§6、§7。
- **摘錄**：

  B 明記：「D-r9-26：v4 補丁本輪不插，等使用者裁。」下表的「已有」指 r09 的 v3 重疊元件，並非 v4 補丁完成。

  | 補丁 | A 的原文節錄 | B 所載 r09 對照 |
  |---|---|---|
  | M1 | 「動靜分離＋三池止漏＋雙視圖」；跑動欄入 `state.json`；`canary` 接管守門，`H24`「純盲測只印不選」；每 pass 原子輸出 `live/_status.json`。 | **未插**；已有活樹狀態視圖，但仍採 H24 熔斷與逐列消融。 |
  | M2 | 「廢手寫 6 逆推器→商空間投影＋32 探針 `sieve`」；三投影縱拆、`uint64` 指紋桶、`info_bits >= 8`、變形自測。 | **未插**；已有三投影、見證格式與 vsplit 冒煙；主迴圈未接見證路徑，`witness_hits` 恆 0。 |
  | M3 | 「金髮女孩鍛造＋SOAR＋誘餌錯解」；橋接熵 ≥4 bits；`p(1-p)×Jaccard` 抽樣；每輪 ≥200 題誘餌。 | **未插**；鍛造爐整步延至 r10。 |
  | M4 | 「Stitch 造詞＋審查入門列（R1～R3）＋影子伴隨編譯」；`guard.py` 三門轉 `gate(post)`；掃 r07 6,000 列 trace；伴隨編譯＋`tx_bundle`。 | **未插**；已有睡眠造詞、ops 孵化三態與快慢道影子，未記載這組補丁驗收。 |
  | M5 | 「殘差棘輪 \(D_q^*\)＋底薪撥款」；鑄模移出 UCB 臂；三臂 20% 底薪＋40% 解題分紅、`escrow`、探針逐次減半。 | **未插**；已有停滯判定與狀態表路由，未記載殘差期貨及撥款驗收。 |
  | M6 | 「S2 19 題預核＋零儀式分段鎖＋共變守門」；`fit_rate`、`@step`、\(G_{\mathrm{valid}}\)、單段留一孵化、失敗段切 `seam`。 | **未插**；已有逐段擬合、常數抽槽、斷裂面；真蠟模產出 0 條 comb。 |
  | M7 | 「雙段封頂位元帳＋邊際帳軟節流」；橫軸納鑄模枚舉與 \(10^5\) 稅；查 `marginal` 軟調成本；`side:learn\|run`、α。 | **未插**；已印 ΔAUC_total、LTO-SCF∪；layer-2 掃描暫存樹 49 筆、活樹 0 筆。 |

- **相關性**：這份對照保留了「完整補丁尚未插入」與「部分基礎元件已存在」的區別，可避免本輪把規格當成現況。

## Q3 N2 CUDA 評估器

- **來源**：
  - A：[ /home/lorkhan/repo/arcagi/reports/native-cuda-1109/prototype.md ](/home/lorkhan/repo/arcagi/reports/native-cuda-1109/prototype.md)
  - B：[ /home/lorkhan/repo/arcagi/native/gpu/driver.cpp ](/home/lorkhan/repo/arcagi/native/gpu/driver.cpp)
  - C：[ /home/lorkhan/repo/arcagi/native/gpu/gpu.hpp ](/home/lorkhan/repo/arcagi/native/gpu/gpu.hpp)
  - D：[ /home/lorkhan/repo/arcagi/native/gpu/space.hpp ](/home/lorkhan/repo/arcagi/native/gpu/space.hpp)
- **摘錄**：

  A，原文節錄與精確數字：

  > 「程式＝長度 1..k 的任意步驟序列」；每題字母表 59～125：D4 七種、upscale／tile／downscale（倍率 1..3）、mirror_tile、crop_bbox、gravity、fill_enclosed、split_overlay（2 軸×5 運算）、self_tile、單對 colormap。
  > 「train 全部完全相同（且 test 輸出合法）＝`exact`」；否則形狀全對時配終端 `fit_colormap`；任何一步失敗或越界（>30）即丟棄。
  > 深度 ≤3、200 題、1.55e8 候選：shared GPU 6.89e7 候選／秒；CPU 6 緒 1.55e6；44.5×；解集合 200/200 一致。
  > 深度 ≤4、12 題、2.01e8 候選：shared GPU 3.01e8 候選／秒；CPU 2.85e6；105×；解集合 12/12 一致。
  > 去重模式：「唯一的長度 P 前綴」×任意後綴；唯一前綴由 CPU BFS 求；因此不列入「同一程式空間」比較。
  > 顯存約 512 MiB；去重深度 5 每題 0.1～6.5 秒、深度 6 每題 0.3～31 秒；峰值 9.2e8 候選／秒。
  > Python 重驗 train：最佳程式 19/19、抽樣 380/380 全對；最佳程式 test 18/19，另 1 支為終端 colormap 過擬合。
  > 呼叫例：`native/bin/gpusearch --tasks reports/native-cuda-1109/bench/tasks-200.txt --depth 3 --mode gpu --samples 20 --out /tmp/s.jsonl`。

  B，介面與限制：

  > `gpusearch --task FILE... | --tasks LIST [--data-dir DIR]`
  > `[--mode gpu|cpu|both] [--depth D] [--stop-first] [--budget SEC]`
  > 「One JSON line per task: program-space size, seconds, candidates/second and solutions per side…」
  > 輸出另含兩側解集合是否一致，以及最低成本的 arcagi JSON 程式；colormap 表已填入。
  > CLI 深度限制：1..8；train＋test 輸入超過 16 pairs 時標記 `too many pairs` 並跳過。

  C，host API 節錄：

  ```cpp
  GpuCtx* gpu_open(unsigned int cap);
  void gpu_load(GpuCtx* c, const DTask& task, const std::vector<uint8_t>& inputs,
                const std::vector<uint8_t>& targets, const std::vector<DStep>& alpha);
  void gpu_set_prefixes(GpuCtx* c, const std::vector<uint8_t>& table, int plen);
  uint64_t gpu_run(GpuCtx* c, int depth, uint64_t start, uint64_t count, std::vector<uint64_t>& sols,
                   bool use_prefix = false, bool shared = false);
  ```

  D：

  > `struct DStep { uint8_t op, a, b, pad; };`
  > `constexpr int MAX_PAIRS = 16;`
  > `constexpr int CELLS = 900;`
  > 候選語言是完全帶參數的格子步驟序列；與 seed AST 空樹語言不同。

- **相關性**：N2 提供了既有 GPU 批次候選評估核心的程式空間、資料介面與同空間速度證據，同時界定它尚未涵蓋的空樹語言。

## Q4 活樹結構

- **來源**：
  - A：[ /home/lorkhan/code/playground-arc1/ws/hammer/README.md ](/home/lorkhan/code/playground-arc1/ws/hammer/README.md)
  - B：[ /home/lorkhan/code/playground-arc1/ws/hammer/_metainfo.json ](/home/lorkhan/code/playground-arc1/ws/hammer/_metainfo.json)、[ /home/lorkhan/code/playground-arc1/ws/hammer/frozen.json ](/home/lorkhan/code/playground-arc1/ws/hammer/frozen.json)
  - C：[ /home/lorkhan/code/playground-arc1/ws/hammer/ops.jsonl ](/home/lorkhan/code/playground-arc1/ws/hammer/ops.jsonl)、[ /home/lorkhan/code/playground-arc1/ws/hammer/ledger.jsonl ](/home/lorkhan/code/playground-arc1/ws/hammer/ledger.jsonl)
  - D：[ /home/lorkhan/repo/arcagi/src/arcagi/hammer/epoch.py ](/home/lorkhan/repo/arcagi/src/arcagi/hammer/epoch.py)
  - E：[ /home/lorkhan/code/playground-arc1/ws/hammer/live/_status.json ](/home/lorkhan/code/playground-arc1/ws/hammer/live/_status.json)，及同樹目錄列舉。
- **摘錄**：

  A，檔案格式與用途：

  > `ops.jsonl`：「操作表（comb／decomp／route／gate／sieve 列，含狀態與證據）」。
  > `ledger.jsonl`：「只增不改的事件記錄」。
  > `nodes/<n>/inbox, outbox, _witness.jsonl`：「收訊、回覆、見證（反向子目標）」。
  > `foundry/requests/{pending,done}`、`foundry/wax`：「鑄模請求與蠟模」。
  > `epochs/<n>/{curve.csv,solutions.jsonl,blocks.json,status.json}`：「每個 epoch 的結果」。
  > `ops/<id>/`：「各 comb／decomp 列的可 `cat` 資料夾」。
  > `live/_status.json`、`live/events.jsonl`、`live/daemon.{pid,log}`：「即時狀態、事件流、daemon 資訊」。
  > 訊息寫入 `nodes/<節點>/inbox/<時間>.json`；epoch 邊界讀取，每封產生 ledger 與 `outbox/<時間>.reply.md`。

  B：

  > 根節點：`"kind": "tree"`；`"entry": "arcagi.hammer.epoch:run_epoch"`；讀取 `frozen.json`、`ops.jsonl`。
  > frozen schema：`hammer-frozen/1`；`h24_floor: per-epoch no regress`；L 預算 100000、P0 25000、P_cap 400000、epochs 8、LLM 稅 100000。

  C，精確計數及 ledger 前三筆：

  > `ops.jsonl`：21 列＝comb 12、decomp 2、gate 1、route 6；sieve 0；live 11、dormant 10、incubating 0。
  > op 欄位包括 `id/kind/payload/status/evidence/born/by/env_hash/tried_env_hashes/ttl`；這是可被搜尋及升降的算子表。
  > `ledger.jsonl`：34 行；第 1 筆 `epoch=-1, kind=epoch, by=agent-r09, note=init_root`。
  > 第 2 筆：`epoch=0, kind=incubate, by=sleep, op_ids=["comb_g1_2ff25d9c21"]`。
  > 第 3 筆：`epoch=0, kind=incubate, by=sleep, op_ids=["comb_g1_019b408846"]`。
  > 後續有 promote、demote、epoch、foundry request／ingest；epoch 帳含解題數、logcost、各類 evals；ingest 帳含 segments、fractures、LLM 稅。

  D，一個 epoch 的程式流程節錄：

  > `_inbox(root, n, ops)`；讀 frozen／ops／state／題組後執行 `_main_run`，檢查 H24 熔斷。
  > `# ② gate feed (train-only LOO + MDL, D-r8-6)`
  > `# ③ grow: sleep word-making -> incubating comb rows`
  > `# ④ shadow, fast lane: live + incubating comb (L16 + P, never H)`
  > `# ⑤ stall / route`；stop 時送 foundry 請求，rt_vsplit 可走 Python 拆法慢道。
  > `# ⑥ judge: one promotion batch per epoch`
  > `# ⑦ write epoch files`

  E，現存組成與狀態：

  > 功能節點 7 個：solve、gate、grow、stall、route、judge、foundry；各有 `_metainfo.json`、inbox／outbox、`_witness.jsonl`。
  > `ops/` 有 14 個物化目錄＝12 comb＋2 decomp；與算子表總列數 21 不同。
  > `epochs/` 有 0～8 共 9 個目錄；另見 `shadow_blocks.json`；foundry 有 pending 2、done 1、wax 1，以及 work 下的 JSON／JSONL 擬合檔。
  > 最新狀態：epoch 8、stall=stop、lib_size=3、L16 解 6、P 解 15、H24 解 2、H8 解 0；`live/events.jsonl` 9 行。

- **相關性**：這些檔案顯示本體、審查與改進如何具體表示為資料列、節點及事件帳，也提供本輪可讀取的搜尋對象與狀態規模。

## Q5 N1 蠟模夜跑

- **來源**：
  - A：[ /home/lorkhan/repo/arcagi/src/arcagi/llm/wax/prompts.py ](/home/lorkhan/repo/arcagi/src/arcagi/llm/wax/prompts.py)
  - B：[ /home/lorkhan/repo/arcagi/src/arcagi/llm/wax/fit.py ](/home/lorkhan/repo/arcagi/src/arcagi/llm/wax/fit.py)
  - C：[ /home/lorkhan/repo/arcagi/reports/wax-night-1109/compare/calls-gpt.jsonl ](/home/lorkhan/repo/arcagi/reports/wax-night-1109/compare/calls-gpt.jsonl)
  - D：[ /home/lorkhan/repo/arcagi/reports/wax-night-1109/compare/calls-gemma-4-e4b.jsonl ](/home/lorkhan/repo/arcagi/reports/wax-night-1109/compare/calls-gemma-4-e4b.jsonl)
- **摘錄**：

  A，比較四種提示法，原文：

  > `base`: “the r09 foundry rules only (control).”
  > `prims`: “+ the 32 primitives and "each step = a few nodes of these".”
  > `prims_py`: “+ the primitives as Python helpers P.<name>; each step must be one expression over P (no loops / comprehensions).”
  > `prims_shot`: “prims_py + one worked example on another task.”

  B：

  > 每段 `(S_i, S_{i+1})` 形成一個 `arcbatch --mode seed-sub` 工作；預算 200k nodes，可附 hammer live library。
  > “A step is fittable when a program comes back and re-checks on every pair with the Python interpreter.”

  C，**2026-11-09 23:00:20（臺北時間）讀取快照**；最新紀錄 ts 為 23:00:16。`verified` 欄計蠟模驗證通過；步擬合及全段擬合只計這些通過紀錄：

  | 模型 | 提示法 | 紀錄數 | verified | 可擬合步／總步 | 全段可擬合 |
  |---|---|---:|---:|---:|---:|
  | gpt-6-sol-low | base | 17 | 10 | 8/15 | 4 |
  | gpt-6-sol-low | prims | 16 | 9 | 13/28 | 2 |
  | gpt-6-sol-low | prims_py | 16 | 8 | 10/21 | 4 |
  | gpt-6-sol-low | prims_shot | 16 | 7 | 13/28 | 2 |
  | gpt-6-luna-low | base | 16 | 9 | 1/13 | 1 |
  | gpt-6-luna-low | prims | 16 | 2 | 0/3 | 0 |
  | gpt-6-luna-low | prims_py | 16 | 3 | 0/7 | 0 |
  | gpt-6-luna-low | prims_shot | 16 | 0 | 0/0 | 0 |

  D，精確數字：

  > google/gemma-4-e4b：四種提示法各 32 筆，共 128 筆；每法 verified=0、全段可擬合=0。
  > 合併 C、D 共 257 筆，涉及 16 題；至少一筆 verified 且 all_fit 的題號共 4 個：46442a0e、74dd1130、7fe24cdd、8d5021e8。

- **相關性**：這組資料直接量到不同模型及語言約束提示產出的蠟模，能否在空樹的固定枚舉預算內被符號程式重現。

## Q6 GPU 程式搜尋與符號迴歸文獻

- **來源**：
  - A：[ /home/lorkhan/repo/paper_readings/summarize/2501.17168_EvoGP.摘要.md ](/home/lorkhan/repo/paper_readings/summarize/2501.17168_EvoGP.摘要.md)
  - B：[ /home/lorkhan/repo/paper_readings/summarize/2502.03367_SyMANTIC.摘要.md ](/home/lorkhan/repo/paper_readings/summarize/2502.03367_SyMANTIC.摘要.md)
- **摘錄**：

  A，EvoGP，庫內摘要原文節錄：

  > 「初始化／評估／交叉變異）全部搬上 GPU、做群級（population-level）並行」。
  > 「線性前綴編碼」；三陣列為 `node_type`、`node_value`、`subtree_size`；最大節點數＋NaN padding，形成定形批次張量。
  > 「子樹交換（subtree exchange）」作統一 GPU primitive；超過最大尺寸則判無效、返回原樹。
  > 小中資料採二維 CUDA grid 的混合並行；大資料採純資料級並行；RTX 3090 實測切換點約 10⁴ 資料點。
  > 「CUDA kernel 註冊為 PyTorch 自訂算子」；「全資料常駐 GPU（zero-copy）」。
  > 峰值 >10¹¹ **GPops/s**；對 GPU SRGPU 峰值 304×、對 CPU Operon 18×；支援百萬級族群。
  > 限制：「須預設最大樹節點數」；padding 浪費記憶體；中大資料下群級並行邊際效益遞減。

  B，SyMANTIC，庫內摘要原文節錄：

  > 「互資訊特徵選擇＋自適應特徵擴展＋遞迴 L0 稀疏迴歸」，從 10⁴–10¹⁰+ 候選找低維描述子。
  > 使用輸入與自訂運算子集遞迴擴展 L 層；C²-SISSO 在稀疏迴歸前先限制特徵複雜度。
  > 「開源 PyTorch（易裝、GPU 加速、易平行）」；資訊論複雜度計入輸入／運算子的數量與頻率。
  > benchmark 回復 >95% 真值方程，次佳略過 50%；僅 5 個時間點的導數量測學 Lorenz 方程。
  > 限制：「只探索到最大深度」；摘要未列 GPU 候選吞吐或 CPU／GPU 加速倍率。

- **相關性**：兩篇分別提供不規則程式樹的 GPU 批次演化評估，以及 GPU 張量化候選特徵搜尋的作法與量測素材。

## Q7 神經導引搜尋與庫學習文獻

- **來源**：
  - A：[ /home/lorkhan/repo/paper_readings/summarize/2006.08381_DreamCoder.摘要/01_一句話概括.md ](/home/lorkhan/repo/paper_readings/summarize/2006.08381_DreamCoder.摘要/01_一句話概括.md)
  - B：[ /home/lorkhan/repo/paper_readings/summarize/2211.16605_Stitch.摘要.md ](/home/lorkhan/repo/paper_readings/summarize/2211.16605_Stitch.摘要.md)
  - C：[ /home/lorkhan/repo/paper_readings/summarize/2411.05820_EvoNUDGE_GNN_Guided_GP.摘要.md ](/home/lorkhan/repo/paper_readings/summarize/2411.05820_EvoNUDGE_GNN_Guided_GP.摘要.md)
  - D：[ /home/lorkhan/repo/paper_readings/summarize/2411.17708_GridCoder_ARC_Program_Induction.摘要.md ](/home/lorkhan/repo/paper_readings/summarize/2411.17708_GridCoder_ARC_Program_Induction.摘要.md)
- **摘錄**：

  A，DreamCoder：

  > 「Wake」用識別模型 Q(ρ|x) 依機率遞減枚舉程式；保留後驗最高 k=5 條 beam；程式為多型別 λ 演算。
  > 「Sleep-Abstraction」從解找共同片段、抽成新原語；最小化函式庫描述長度＋重構後程式描述長度。
  > 「Sleep-Dreaming」用 replay 真實解與 fantasy 庫抽樣，各半（50/50），訓練識別模型。
  > 「高階庫函式降低搜尋『深度』，神經識別模型降低搜尋『廣度』」。
  > 8 領域；list 218 題長出約 20 個庫函式；文字編輯 3.7%→79.6%，平均搜尋 235→40 秒。
  > 從 Lisp 極小原語解 20 題約需 5 天／64 CPU；摘要另記總 CPU 成本約一年。

  B，Stitch：

  > 「直接自頂向下合成抽象函數本身」；搜尋帶洞部分抽象，以壓縮效用上界做 branch-and-bound。
  > 「部分抽象的匹配位置是其所有後代的匹配位置超集」；上界亦作優先佇列排序，增量匹配只檢查父抽象匹配位置。
  > U(A)=−cost(A)＋cost（語料）−cost（重寫後語料）；不需實際執行重寫即可計算。
  > 對 DreamCoder 壓縮階段快 3–4 個數量級、省逾 2 個數量級記憶體；Stitch 單緒、DreamCoder 8 CPU。
  > 八領域各 250 支程式：測試壓縮率 2.55×–11.57×；0.19–77 秒；11–714 MB。
  > 限制：原生版純語法匹配、學不了高階抽象；一次學一個抽象；argument capture 剪枝存在有界偏差案例。

  C，EvoNUDGE：

  > GAT 對 application 節點輸出 saliency，「只挑前 k 個最值得擴展的節點」。
  > 節點特徵 79 維；3 層 GAT；以已知目標程式軌跡做模仿學習與二元分類。
  > 一次性訓練：DGX 8 GPU 約 24 小時；之後全部實驗共用同一 GNN。
  > NUDGE 圖中的 value 節點轉為子程式庫 L，再做 library-based 初始化及子樹替換變異；GP 族群 1000、50 代。
  > 自建 1032 題，522 訓練／510 測試；高度 t=6 時成功率 43.42%，GP 31.43%。
  > 總執行時間不到 GP 兩倍；圖變大後 GNN 查詢更貴、導引更不準；saliency 數值目前未帶入庫。

  D，GridCoder：

  > VLM 輸出 DSL token 機率，再以聯合機率排序枚舉、逐一驗證；「非執行引導」。
  > 條件獨立假設將機率攤為位置×類別；只需幾次推論，6 次不同範例對／起始 token 取均值。
  > 雙 CNN＋單層 transformer 解碼器，452M 參數；DSL 74→89→98 原語，V1 約 5M 合成樣本。
  > DSL 可解的 29 題子集：79.3%；MCTS＋VLM 69%、VLM-only 13.8%。
  > 10 個結構 OOD 任務只解 1 個；LTS 執行引導只有 proxy，未真正實作訓練。

- **相關性**：這四篇涵蓋神經模型對搜尋排序與剪枝的具體角色，以及從既有解抽出新原語的庫學習過程，並保留其訓練成本與泛化限制。

## Q8 aos 體系自我改進現況

- **來源**：
  - A：[ /home/lorkhan/repo/arcagi/notes/rounds/總表/使用者方向.md ](/home/lorkhan/repo/arcagi/notes/rounds/總表/使用者方向.md)
  - B：[ /home/lorkhan/repo/arcagi/notes/rounds/r08/r09-使用者七條原話.md ](/home/lorkhan/repo/arcagi/notes/rounds/r08/r09-使用者七條原話.md)，意見 2。
  - C：[ /home/lorkhan/repo/simple_tools/aos/proto8/thinking/2026-11/07/arknights-kb/28-帶去arcagi清單.md ](/home/lorkhan/repo/simple_tools/aos/proto8/thinking/2026-11/07/arknights-kb/28-帶去arcagi清單.md)
- **摘錄**：

  A，使用者原話及該檔明列量法：

  > 原話：「除此之外，我會希望arc agi這塊，把主要精力放在元優化。用於解決的訓練集只需要少少幾個就好，重點在於優化出能夠以最高效率最快解決問題的aos樹。途中可以繼續元優化這個元優化流程」
  > 原話：「關於產出積木這件事，是否可以不經過llm？」；回答後說「可以」。
  > 原話：「arc agi的題目以2d為主，但aos的優化卻是偏向於程式流程。兩者都可以用符號迴歸配合llm，最終目標是能夠從零開始，在對目標題目(arcagi)完全無認知的情況下，配合無神經網路的優化器，成長到能夠解決問題」
  > 彙整量法：「從空基準學到解出一小組題（5～20 題）的學習曲線：多快、多省（秒、token、LLM 呼叫、輪數）」；evaluation 偶爾量泛化。
  > 彙整量法：「從真正空的樹起跑的學習曲線（tag 前 diff aos/blocks/、aos/pool/）」；手寫原語與 r01～r06 成績當對照組。
  > 11-09 放寬原話：「兩個都試試看。cuda神經網路也是可以拿來符號邏輯，暴力搜索。」

  B，低成本審查與改進的原話：

  > 「我們現在看到的所謂審查與改進，都是以llm agent爲主體。但實際上這算是成本較高的通用改進方式。對於功能單一的節點來說，其審查與改進可以變得很...低廉？比如一個x=2*y公式節點，他的審查可能就是跑一個固定程式，看他過去十次任務的成功率，而改進，可能就是跑符號回歸走暴力解。將這套東西稍微往上，比如那個審查用的固定程式稍微進化一點，可能會加上不少的判斷之類，而改進這塊，因爲符號回歸花時間，所以搞不好會變成另一個程式，只做一些特定替換。」

  C，arknights 量法原文節錄與精確數字：

  > 「量改進過程」的尺和帳：題數曲線、空基準重置重跑、兩條基準量雜訊、元審視可核預測、改進花費另記帳。
  > 第五輪 v1：要問 AI 的題 184→168，−9%、雜訊 0；已知答案 124→約 435；整個任務不用問 AI 的仍為 0 個。
  > pass 重置：「一次試驗從空知識的基準 tag 起跑，pass 之間只把產物（庫）倒回、學到的知識留著」。
  > 空基準防汙染：「打或重打 tag 前一定 `git diff --stat base-v0 <tag> -- ws/defs`」；只該看到碼的差。
  > 「同一個基準跑兩次，兩條之差就是雜訊尺」；驗證真值「不餵升降、不餵梯度」。
  > 元審視每份至少一條可核預測；「補真值少 2～10 題」實際少 16 題；驗證覆蓋預測錯，仍為 0。
  > meta 帳獨立且不隨試驗重置；第五輪 7 筆、約 223 萬 token、2,665 分，約一整條試驗的分數。
  > 規則 candidate→shadow→live；同題按 qid 去重；門檻先預核；三條試驗驗證 4 任務的 live 覆蓋均為 0。

- **相關性**：這些原話與實測量法將本輪目標定位於 aos 樹及其改進流程的學習效率、成本與泛化，而非單次 ARC 解題數。

## 未找到

- 指定的 `paper_readings/index/` 與 `summarize/` 範圍內，未找到 **TensorGP、cuML／CUDA GP 的專篇**；找到的是 EvoGP 及其他 GPU／符號迴歸相關摘要。
- 截至 **2026-11-09 23:00:20**，尚無 `/home/lorkhan/repo/arcagi/reports/wax-night-1109/overnight/`、`overnight-summary.md` 或 `compare/summary.md`；Q5 數字來自當時存在的呼叫 JSONL。
- r09 收尾文件未提供 **v4 M1～M7 已插入並完成驗收**的紀錄；文件明記本輪未插，不能以重疊元件替代補丁完成證據。