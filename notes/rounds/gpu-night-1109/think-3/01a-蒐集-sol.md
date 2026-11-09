# 01a 蒐集（sol）

蒐集截點：2026-11-10 00:26–00:27（Asia/Taipei）。全部唯讀；未重跑搜尋、測試或 GPU 基準。以下區分既有報告、現場讀檔統計與依原始碼判讀；長跑數字均非最終結果。

## Q1｜N2 GPU 窮舉格子步驟

來源：[reports/native-cuda-1109/prototype.md](/home/lorkhan/repo/arcagi/reports/native-cuda-1109/prototype.md:7)，重點見第 11–38、45–52 行。

- 同程式空間、CPU 6 執行緒對照：深度 ≤3，training／evaluation 各 100 題，共 1.55e8 候選；`k_shared` **44.5×**，`k_flat` 48.9×。深度 ≤4，12 題、2.01e8 候選；`k_shared` **105×**，`k_flat` 48×。212 題的**完整解集合逐題一致**。
- 字母表每題 59–125 個帶參數步驟。GPU 支援 D4 七種，以及 `upscale/tile/downscale`、`mirror_tile`、`crop_bbox`、`gravity`、`fill_enclosed`、`split_overlay`、`self_tile`、單對 `colormap`；物件、cells、`x_*` 原語尚未齊備。
- `k_shared` 每執行緒負責一個前綴，快取第一組 train 的前綴狀態，再試最後一步。觀測等價前綴去重仍由 **CPU BFS** 建立。
- 去重模式：深度 5、P=3，6 題各 0.1–6.5s；深度 6、P=4，3 題各 0.3–31s；峰值 9.2e8 候選/s。這組不屬於同空間 CPU 對照。
- Python 重驗：最佳程式 19/19、抽樣 380/380 **train 全對**；最佳程式 **test 對 18/19**。`25d8a9c8` 是 `tile＋downscale＋7 列 colormap` 的過擬合。
- 量測時與 LM Studio 共用 GPU，報告記載顯卡已被占用 86–92%；單程序約 512 MiB 顯存。

長跑現場統計：

- [overnight/phase-A.jsonl](/home/lorkhan/repo/arcagi/reports/native-cuda-1109/overnight/phase-A.jsonl)：795 筆題目結果，其中 73 題有 C++ train 擬合解；790 筆標 `complete=true`。**尚無 test 重驗彙總**。
- [filler/train-open-d6.jsonl](/home/lorkhan/repo/arcagi/reports/native-cuda-1109/filler/train-open-d6.jsonl)：20 筆、0 題有解；evaluation 同名檔為 38 筆、0 題有解。深度 6 完成筆數分別為 19、36。
- 查找含忽略檔後，未見 `overnight-summary.md` 或 filler Markdown 彙總；計畫中的 800 題、後續 B／C 階段不能當成已完成結果。

**相關性：**這條線證實 DStep 候選評估可大幅加速，但尚未量到完整 seed／hammer AST 搜樹的加速。

**未解問題：**長跑最終覆蓋幾題、test 真對幾題、主線新增幾題？CPU 前綴去重占端到端多少時間？

## Q2｜N3 GPU 遺傳符號搜尋

來源：[reports/gpu-gp-1109/report.md](/home/lorkhan/repo/arcagi/reports/gpu-gp-1109/report.md:11)、[progress.md](/home/lorkhan/repo/arcagi/reports/gpu-gp-1109/progress.md:1)。

個體是長度 1–10 的 DStep 索引序列，共用 N2 GPU 原語與判解；適應度為 `0.5 格子相符＋0.35 colormap 相符＋0.15 形狀−0.002×長度`。

族群調校在題 `6e19193c`、15s、與 N2 共用 GPU 下：

| pop | 功耗 | eval/s | 代數 |
|---:|---:|---:|---:|
| 65,536 | 93 W | 1.02e7 | 2,328 |
| 524,288 | 125 W | 1.89e7 | 543 |
| 2,097,152 | 114 W | 1.45e7 | 104 |

整夜採 524,288，約 0.5 GB；比較實驗 GP／random 都用 65,536。

同題、同原語、每題相同秒數的結果；各格為 **train 擬合／Python test 全過**：

| 題組 | 題數／每題預算 | GP | random | 窮舉 |
|---|---|---:|---:|---:|
| real，主線未解 | 40／20s | 1／0 | 0／0 | 0／0 |
| synth-L5 | 16／15s | 16／16 | 12／12 | 16／16 |
| synth-L6 | 19／15s | 18／17 | 14／13 | 18／17 |
| synth-L7 | 16／15s | 15／12 | 11／10 | 14／12 |

- 合成題已驗深度 <4 無解，但窮舉多在深度 4–5 找到等價短解；植入長度 5–7 不等於最短解深度。
- 解題中位時間，GP 對窮舉：L5 **0.57／0.30s**、L6 **0.59／0.45s**、L7 **0.91／0.31s**。兩者都解時，GP 有 16 題較長，沒有較短。
- 報告列窮舉約 6e7 候選/s，GP 約 9e5「個體×train」/s，並明說**量綱不同**，不能直接當精確吞吐倍數。
- real 唯一 GP 擬合解 `1fad071e`，train 過、test 錯。整夜早期前 232 題，C++ 判 7 題 solved，Python train 全過，test 僅 `a79310a0` 正確，即 1/7。
- L7 的 test 總數相同，但各有獨得：GP `22eb0ac0-L7`、窮舉 `d037b0a7-L7`。不能把總數打平解讀成解集合相同。
- 報告 real 表寫 `d7`，後文過擬合段寫「8 步」，計數口徑尚有不一致；未見最終 overnight Markdown 彙總。

**相關性：**現有比較同時提供尋解時間與泛化落差，能區分「更快找到 train 擬合」和「更快得到有效解」。

**未解問題：**最終真題結果如何？較深且已排除短等價解的題組上，GP 是否仍有優勢？`1fad071e` 深度如何統一計數？

## Q3｜N5 forbid 剪枝

來源：[reports/seed-forbid-1110/report.md](/home/lorkhan/repo/arcagi/reports/seed-forbid-1110/report.md:5)、[seed-gpu-可行性.md](/home/lorkhan/repo/arcagi/reports/seed-forbid-1110/seed-gpu-可行性.md:7)。

- `forbid` 在主列舉器根部、**求值前**擋 AST 樣式；不算節點、不進 bank，另記 `forbidden`。
- training 前 100 題、decomp 開、4 執行緒：9 條規格樣式擋 **0.46–1.37%**；加 10 條冪等樣式後擋 **1.35–3.14%**。
- 預算 1e6、三次交錯計時，task 秒中位數：base **35.90**、9 條 **36.67**、19 條 **33.75**。報告判定差距 −2%～+6% 落在重跑雜訊內。
- 1e5／1e6／1e7 的 train 對題數依序 4／7／10，test 對 4／5／7；各設定的題目集合與程式完全相同。
- 原文：「被擋的幾乎全是『值跟某個子項一樣』的程式，本來就會被 bank 去重丟掉。」因此主要省的是少數候選的求值，bank 幾乎不變。
- 只擋主列舉器根部；**BodyPool 與 cond 見證未套用**。r09 的「77% 等價重複」未被這組根部兩層樣式涵蓋。
- 可行性報告把 CPU 工作拆為組合、求值、hash-cons、去重、命中；其中 hash-cons 約 37% 熱點是引用既有 r09 量測。30–100× 等數字是當時**預估**，不是 seed 端到端實測。

**相關性：**這組實測界定了現有樣式剪枝能省的工作量，不能用被擋數取代整體搜樹速度。

**未解問題：**更大樣式集能涵蓋多少重複？非單純等價樣式在更大題組是否掉題？BodyPool／cond 的可剪比例尚未量測。

## Q4｜N5b seed 一階層 GPU

來源：[reports/seed-gpu-1110/report.md](/home/lorkhan/repo/arcagi/reports/seed-gpu-1110/report.md:7)、同夾 [run-L3.jsonl](/home/lorkhan/repo/arcagi/reports/seed-gpu-1110/run-L3.jsonl) 與 `run-L6.jsonl`。

- 條件：100 題整層一次 GPU launch；CPU 是真 Enumerator、4 執行緒。空 library、不分解，兩邊排除未支援原語；GPU kernel 取 20 次量測。
- 支援 20 種：`add sub mul neg mod eq lt max min and or not len nth head last take drop reverse transpose`。
- 排除 12 種：`if cons append concat range repeat count sort map filter zipwith fold`；library block 也不支援。
- 2–6 層逐題新項目指紋集合與節點數皆一致，100 題零不一致、零 unsupported。

| 層 | 節點數 | GPU kernel 平均吞吐 | 對 CPU4 |
|---:|---:|---:|---:|
| 2 | 1,439 | 1.5e6/s | 0.13× |
| 3 | 59,560 | 1.42e8/s | 2.6× |
| 4 | 103,419 | 3.1e8/s | 7.0× |
| 5 | 593,270 | 8.7e8/s | 16× |
| 6 | 1,366,652 | 1.37e9/s | 30× |

- packed bank 規模：L3 執行檔首筆為 **8,130 items／154,314 cells**；L6 為 **207,477 items／6,149,574 cells**，均為跨 100 題總量。
- 報告記 bank 上傳約 12–38ms，**未計入倍數表**；L6 原始檔逐層實際列約 6.94–22.17ms。顯存最高約 133 MB。
- CPU 計時含 choose、型別 unify、hash-cons、勝者 PP 建樹；GPU 倍數只含生成、求值、雜湊、去重，**不含 host unify、上傳、勝者物化**。
- 小層 kernel 約 0.4ms；報告指出每執行緒整張 grid 雜湊的長尾。64-bit 指紋有理論碰撞風險；目前比對未見碰撞。

**相關性：**0.13×→30× 隨批量增大出現，描述的是受限一階片段的成本，不能直接外推完整 seed 搜樹。

**未解問題：**單題而非 100 題合批時的損益點在哪？含上傳、unify、物化後多少倍？擴大值域與原語後是否仍一致？

## Q5｜N5c 端到端

來源：[reports/seed-gpu-e2e-1110/progress.md](/home/lorkhan/repo/arcagi/reports/seed-gpu-e2e-1110/progress.md:5)；截點未見 `report.md`。

原始暫存來源目錄，以下稱 **E**：

`/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n5c/`

- 進度原文：「`--gpu-seed is slower end to end at 1e6 (wall 18.8 s vs 8.0 s)`」，背景有另 7 個 GPU 程序。
- training 前 100 題、decomp、4 緒；1e6 的 CPU／GPU 門檻 20k、200k、1e6 結果一致。另 1e5、門檻 1 的驗證重查 **6.25M SKIP/NODE 判定，0 失敗**。
- 現場重讀 `E/res-1000000-*.jsonl`：九次執行每題結果，忽略 `seconds/eval_steps` 後，相對 CPU 第一輪 **0 題不同**；均 92,571,392 節點、train 對 7、test 對 5。

[實際 wall.txt](/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n5c/wall.txt) 的外層牆鐘：

| 預算 | 模式 | 完成次數 | wall 中位數 |
|---|---|---:|---:|
| 1e6 | CPU | 3 | 9.099s |
| 1e6 | GPU，min=20,000 | 3 | 21.138s |
| 1e6 | GPU，min=200,000 | 3 | 9.094s |
| 1e7 | CPU | 1 | 129.426s |

1e7 CPU 第一輪已完成，train 對 10、test 對 7；GPU 第一輪 JSONL 當時仍為空，**尚無 1e7 GPU 比較及三次中位數**。

時間分布與開銷，來源 `E/r100_cpu_1e6.err`、`E/r100_gpu_1e6.err`：

- CPU 累加 Enumerator 時間：`run_s=30.784822`、`sup_s=8.129063`、`other_s=22.641926`；一階支援段約 **26.4% 時間、66% 節點**。這些是跨執行緒累計時間，非 wall。
- 原文 `lambda/other 74%` 的 **74% 是合併 other 桶**。原始碼沒有把 lambda、if、library 各自分開；也包含其餘不支援片段，不能稱 lambda 單獨占 74%。
- GPU 記錄 1,253 個 Enumerator、836 個 GPU 層／chunk；`gpu_s=11.640670`、`sync_s=22.605124`。除以 836，約為 **13.9ms launch＋wait／chunk、27.0ms sync／GPU 層**；sync 不只是純 PCIe 傳輸。
- 同一 Enumerator 可追加同步；新 Enumerator／分解子題從自己的 bank 重新上傳，未跨子題共用。
- 依這次 CPU 比例，令支援段成本降為零且沒有新增開銷，Enumerator 的 Amdahl 上限約 `1/(1−0.264)=1.36×`；進度以四捨五入寫約 **1.35×**。

**相關性：**此線直接量到完整搜尋中批量門檻、CPU 剩餘工作及傳輸同步對局部 kernel 加速的抵銷。

**未解問題：**1e7 完整結果與無 GPU 競爭基準？other 各部分占比？重複 bank、CPU 勝者處理各耗多少？200k 門檻實際啟用多少 GPU 層？

## Q6｜N4 gpuprofile 題目特性

來源：[progress.md](/home/lorkhan/repo/arcagi/reports/task-features-1109/progress.md:6)、[gpuprofile-spec.md](/home/lorkhan/repo/arcagi/reports/task-features-1109/gpuprofile-spec.md:32)、[native/tools/profile_features.py](/home/lorkhan/repo/arcagi/native/tools/profile_features.py:1)。

- 與 N2 同 DStep 空間，但每支程式都算 train 接近程度，不因 mismatch 提早淘汰。
- `denom=Σ max(產出面積,目標面積)`；`raw` 是重疊區原色相符數／denom；`cm` 是跨 train 共用最佳單一 colormap 後相符數／denom，排名用 cm。
- 每深度保留候選池 M=64，CPU 依 train 輸出簽章去等價、留 K=8；輸出 space、valid、fail、perfect、耗時、完成／截斷標記、分數直方圖與 top-K。
- 抽查記錄：`3c9b0459` d1 top-1 `rot180=1.0`；`00d62c1b` 的 `fill_enclosed` 為 cm=1.0、raw=0.933。
- 截點原始 `profile/training-d5.jsonl` 有 **182 題**，best=1 有 26、best≥0.9 有 81；evaluation 有 **187 題**，分別為 12、70。合計 369 題；是部分結果，非 800 題最終統計。
- **features.csv、README.md 尚不存在**，`profile/finalize.log` 為空；進度中的「800 列、62 欄」指前 5 題剖面測過的整表管線，不代表 800 題已剖析。

依 `profile_features.py` 現有程式重建的 **62 欄**，不是已存在 CSV 的實讀表頭：

- 基本／CPU 23 欄：`task, split, mainline_solved, n_train, n_test, in_h_mean, in_w_mean, out_h_mean, out_w_mean, same_shape, out_shape_const, size_ratio_y, size_ratio_x, area_ratio_mean, colors_in, colors_out, colors_new, colors_dropped, objects_in_mean, objects_out_mean, changed_cell_frac, identity_score, profiled`。
- GPU 22 欄：`alphabet, dedup, max_depth, depth_reached, seconds, space_total, valid_total, best, best_depth, perfect_depth, perfect_total, ge90_total, top1_score, top1_raw, top1_program, n_top, best_d1…best_d6`。
- 17 個 `prim_*` 欄：`flip_lr, flip_ud, transpose, rot90, rot180, rot270, anti_transpose, upscale, tile, downscale, mirror_tile, crop_bbox, gravity, fill_enclosed, split_overlay, self_tile, colormap`，前綴均為 `prim_`。

CPU 特徵描述題目尺寸、顏色、物件與變化；GPU 特徵描述**在指定語言及預算下**哪些原語／深度接近答案。`prim_*` 是各深度保留 top 程式中含該原語的比例，不是全部候選頻率；best=1 表示 train 擬合，不保證 test。

**相關性：**剖面已能記錄題目特徵與實際搜尋結果的對應，但尚無其提升搜尋排序速度的量測。

**未解問題：**最終 800 題覆蓋與截斷率？CPU 特徵和搜尋剖面的預測關係？分數有多少來自背景色或 colormap 擬合？

## Q7｜think-2 的 GPU 決定

來源：[代定清單.md D6](/home/lorkhan/repo/arcagi/notes/rounds/gpu-night-1109/think-2/代定清單.md:14)、[02-規劃-fable.md](/home/lorkhan/repo/arcagi/notes/rounds/gpu-night-1109/think-2/02-規劃-fable.md:120)、[02b-Argon審.md](/home/lorkhan/repo/arcagi/notes/rounds/gpu-night-1109/think-2/02b-Argon審.md:15)。

- D6 原文：「**不投；GPU 只做題目特性旁路**」；理由為現有 gpusearch／GP 只評單支格子步驟程式、沒有樹介面。翻案點：下一輪立 `native/gpu/ast/`、顯存 ≤1GB；並標記與使用者「能用 GPU 就用」有衝突。
- fable 第 120 行：hammer comb body 是 `map/lam/append/reverse` 的 list-of-list AST，現有 GPU 核吃 DStep；題目特性旁路「**不進適應度**」。
- 第 158–159 行：建議當輪不投 AST 核，預估 CPU 限制約每小時 20–30 個個體；此為規劃估計，非本次實測。
- 第 177 行另寫「不寫 GPU AST 核；不碰 ≥3 GB 顯存」。因此文件有下一輪目標 ≤1GB，以及另一處核規模／當輪邊界的 3GB 敘述，並非已測顯存。
- Argon 審全文未找到 `GPU/CUDA/顯卡/旁路` 的直接段落，**未見它直接裁定 D6**。與搜尋行為相關的明確批評是第 15–17 行：依 id 重排 ops 列會改同優先權枚舉先後，在固定預算下改變搜尋軌跡。

**相關性：**D6 是當輪的範圍代定與介面缺口記錄，不能作為 AST 搬 GPU 不可行的實驗結論。

**未解問題：**D6 是否已被使用者翻案？seed AST 與整棵 hammer 樹各要評估到哪一層？顯存驗收口徑如何統一？

## Q8｜使用者方向原話

來源：[notes/rounds/總表/使用者方向.md](/home/lorkhan/repo/arcagi/notes/rounds/總表/使用者方向.md:25)。以下只摘引號內原話，與文件作者的後續解釋分開。

- 第 28 行：「這其實有點空轉，這也是有收益，但我一直在說的是，想要弄出能更快搜尋或更快解決出題目的aos樹，而非解題。這也可以啦，可以去取得題目特性，用以後續的其他訓練」
- 第 39 行：「兩個都試試看。cuda神經網路也是可以拿來符號邏輯，暴力搜索。」
- 第 31 行：「然後成本這塊也是，單純的符號回歸就是比較花時間，但也可以讓agent參予，就變成花token」
- 第 50 行：「除此之外，我會希望arc agi這塊，把主要精力放在元優化。用於解決的訓練集只需要少少幾個就好，重點在於優化出能夠以最高效率最快解決問題的aos樹。途中可以繼續元優化這個元優化流程」
- 第 30 行：「或者說不是同步搜尋，而是分層式改進。比如D-E-F這棵樹的改進流程，可能會將一些梯度(改進責任)分配給D，然後D進行改進這件事，等同跑A-B-C的審查/改進。」

第 38 行另以轉述記載：可暴力吃 CPU、可寫 CUDA，設備 RTX 5060 Ti 16GB；這一行不是逐字引語。

**相關性：**明確目標是改進 aos 樹的搜尋／解決效率，GPU 解題結果與題目特性是可供衡量或訓練的材料。

**未解問題：**速度、節點數、GPU 秒、token、泛化各自的正式比較權重，原話未給固定數字。

## Q9｜lambda、if、library 的實作與求值

已以 `rg` 定位並讀原始碼。下列「卡點」是依現有實作判讀，未實作或量測新 GPU 核。

### lambda

來源：[native/src/seed_enum.cpp](/home/lorkhan/repo/arcagi/native/src/seed_enum.cpp:261) 的 `BodyPool`（261）、`lambdas`（338）、`choose`（715）、`eval_prim`（793）；[seed_value.cpp](/home/lorkhan/repo/arcagi/native/src/seed_value.cpp:528) 的 MAP／FILTER、ZIPWITH、FOLD、`call`（583）、`eval`（589）。

`BodyPool` 依型別、body 大小與 probe 值去重，展開／編譯 lambda；套用時綁定當前輸入，再逐元素 `call→eval`。fold 的 accumulator 逐元素相依。

**GPU 卡點：**現有核未表示 Arena 函數節點及遞迴環境；還涉及變長 list、Store hash-cons、錯誤／步數限制，fold 本身另有元素間順序相依。

### if

來源：[seed_value.cpp:441](/home/lorkhan/repo/arcagi/native/src/seed_value.cpp:441)、[seed_enum.cpp:877](/home/lorkhan/repo/arcagi/native/src/seed_enum.cpp:877)。

`apply_prim(IF)` 只選值；但 `eval` 先求全部子項、遇 ERR 即回傳，**現有語義不是 lazy branch**。`cond_witness` 另由 bank 建 train 命中 mask／布林 mask，選相容 then／else 並組 if。

**GPU 卡點：**三元值選擇、任意回傳型別及錯誤語義未在現有一／二元 job 路徑完整支援；cond 的 bank mask 搜尋也是另一段工作，不能只搬一個條件選擇。

### library

來源：[seed_enum.cpp:73](/home/lorkhan/repo/arcagi/native/src/seed_enum.cpp:73) 的 `expand_rec`，以及同檔 `build_ops`（169）、`run_expanded`（658）、`emit`（782）。

`blk` 先查庫、遞迴展開 body、代入 holes，再 compile 到 Arena、逐 train eval；搜尋成本上 block 可算一節點，實際執行仍是展開後程式。

**GPU 卡點：**目前沒有通用展開 AST 評估路徑；block 內可含 lambda、變長 list 與巢狀呼叫，不能直接套固定一階 opcode。

現有 GPU 明確邊界來源：[native/gpu/seed/seed_enum_gpu.cpp:806](/home/lorkhan/repo/arcagi/native/gpu/seed/seed_enum_gpu.cpp:806)：

```cpp
if (op.prim < 0 || op.block || !gpu_prim(op.prim)) return false;
for (bool l : op.lam_pos) if (l) return false;
```

[e2e_kernel.cu:197](/home/lorkhan/repo/arcagi/native/gpu/seed/e2e_kernel.cu:197) 每 chunk 跑 `k_eval→k_resolve→status 回傳→cudaStreamSynchronize`；勝者仍回 CPU 走原 `emit`。

**相關性：**原始碼把未搬工作的語義與執行成本定位清楚，也說明它們未包含在 N5b 的 30× 內。

**未解問題：**other 中三類各占多少？lambda body、block 展開與值池的實際尺寸分布？GPU 可支持的語義子集尚未定量。

## Q10｜排序器、先驗與可用訓練材料

查找範圍：`src/、native/、scripts/、docs/、reports/、notes/rounds/gpu-night-1109/` 的相關文字與程式，使用 `ranker/prior/排序`，並補查 recognition、常見 ML 函式庫名稱及檔名。

**已有使用次數先驗：**

- [src/arcagi/grow/compress.py:193](/home/lorkhan/repo/arcagi/src/arcagi/grow/compress.py:193)：`order_from_uses` 回傳 `log(1+uses)`。
- [grow/curve.py:239](/home/lorkhan/repo/arcagi/src/arcagi/grow/curve.py:239)：learn 開啟且 order=prior 時使用；第 313–315 行由 feed 程式中的 op 累加使用次數。
- Python [seed/lam.py:63](/home/lorkhan/repo/arcagi/src/arcagi/seed/lam.py:63) 與 C++ `native/src/seed_enum.cpp:191–198` 均依先驗權重排序，平手保留表順序。這是統計先驗，非神經 ranker。

**已有資料或記錄工具：**

- [reports/curve-r07/dec-g1g4/seed0/solutions.jsonl](/home/lorkhan/repo/arcagi/reports/curve-r07/dec-g1g4/seed0/solutions.jsonl)：實讀 216 列，含 `program、near_top、nodes_to_first、seconds、train_ok、test_ok、pass、source` 等欄。45 列 train_ok，但依程式 JSON 去重僅 **8 支程式、5 題**；列數不能當獨立正例數。
- [native/tools/seed_record.py](/home/lorkhan/repo/arcagi/native/tools/seed_record.py:1)：可記每次分解子搜尋的 examples、型別、預算、找到程式、節點數與 near 結果；用途原為 parity，比對材料尚未直接變成 ranker 訓練管線。
- N2 已有 399 支 Python train 重驗通過的 DStep 樣本；N4 已有部分題目的 top-K、近似分數、原語分布；N3 有 GP／random／窮舉比較輸出。**這些資料的語言與去重口徑不同**。

**未找到的部分：**在上述範圍未見已落地的神經 ranker 訓練程式或權重。夜跑 `cuda-白話.md` 明記「沒做：小網路排序器」；[think-1 規劃](/home/lorkhan/repo/arcagi/notes/rounds/gpu-night-1109/think-1/02-規劃-fable.md:96) 記「≥200 支 train_ok 程式後再訓練」，這是規劃門檻，非已完成驗收。

**GPU 能否產資料：**已有 gpuprofile 輸出程式／分數／搜尋量，以及 N2 程式重驗樣本，證明可產生 DStep 搜尋監督材料；尚未證明這些材料可改善 seed／hammer 排序速度，也沒有已驗證的跨語言標籤映射。

**相關性：**目前同時存在可執行先驗與可再加工搜尋紀錄，但尚無「訓練 ranker 後搜樹變快」的閉環結果。

**未解問題：**可用且去重後的 seed 正例共有多少？排序標籤是命中、節點節省或 GPU 秒？負例、分池及 test 資訊如何隔離？

## 跨題未解問題

- N2／N3 最終長跑覆蓋、test 重驗與主線新增解尚缺彙總。
- N5c 1e7 GPU 結果、三次中位數及無 GPU 競爭基準尚未齊備。
- `other≈74%` 尚未拆出 BodyPool、lambda 套用、if、library 與其他原語耗時。
- 單題、合批、含上傳與物化的加速口徑尚未統一。
- 分解子題 bank 重傳與每層同步，各自占 wall 多少尚未分離。
- DStep、seed AST、hammer 整樹的 GPU 評估邊界與資料映射尚未打通。
- 合成深題仍可能有短等價解，尚缺能確認最低解深度的比較題組。
- 高分／train_ok 樣本的跨題泛化、背景色偏差與過擬合比例尚未完整量測。
- ranker 正例去重、負例、分池及「每單位成本節省多少搜尋」標籤尚未形成驗證管線。