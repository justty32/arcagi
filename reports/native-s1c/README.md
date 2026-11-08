支線 S1 第三任：native 改成「小題組快評測引擎」（arcbatch），並在 native 這段加支持度守門，收「過 train 卻答錯」。

← 第二任 [05 第二輪](../native-s1/05-第二輪.md)｜第一任 [04 總結](../native-s1/04-總結.md)｜交棒 [交棒.md](交棒.md)

## 結論

- **arcbatch**（`native/bin/arcbatch`＝`arcsearch --batch`）：一個行程跑「題 × 設定」，C++ 執行緒並行，不經 Python。20 題小集（training，seed 7）節點預算 25k：**7 題、CPU 2.4 秒（6 執行緒估牆鐘 0.4 秒）**；同一批題 r06 混合入口要 146.6 秒（逐題加總），其中光 Python search 那段就 34.4 秒，解 9 題（Python 7、native 補 2）。第二次跑同設定讀快取，0.0003 秒。
- **單執行緒速度**：物件抽取的快取鍵改成一格一個位元組、編譯改 `-O3 -march=native -ffp-contract=off`，同一題 40 萬節點從 3.83 秒降到 2.22 秒（1.7 倍）。程式與節點數跟舊 binary 完全一致（抽 3 題比對 solutions、nodes；1 與 6 執行緒輸出逐行一致；`tests/native` 全綠）。
- **支持度守門**（只用 training 定）：以 `local_rule`／`x_vrule` 結尾的程式，要求「train 輸出總格數 ÷ 表的列數」≥ 4（整個程式就是這張表）或 ≥ 16（表前面還有別的步驟）。在 r06 native 會答題的 training 題上：**答錯 26 → 9，答對 18 → 18**。

## arcbatch 用法

```
native/bin/arcbatch --tasks LIST [--data-dir DIR] [--task FILE ...] [--configs CONFIGS.jsonl]
                    [--threads 6] [--cache DIR] [--dump] [--spec PATH] [--out RESULTS.jsonl]
```

- `LIST` 每行一題：題檔路徑（相對於清單所在資料夾），或配 `--data-dir` 寫題號。`#` 開頭略過，空白或逗號之後的字略過。題檔要有 test 的 output 才能算 `test_correct`。
- 設定檔每行一個 JSON，欄位都可省略：

| 欄位 | 意思 | 預設 |
|---|---|---|
| `name` | 設定名 | `default` |
| `prims` | 原語白名單（只限制搜尋時列舉哪些；空 list＝全關） | spec 全部 |
| `drop` | 原語黑名單 | 無 |
| `macros` | `{名: [[原語, 參數…], …]}`，加進搜尋；macro 可以引用別的 macro（展開後只能用 C++ 已移植的原語） | 無 |
| `learners` | 開哪些 learner：`colormap`、`colormap_step`（colormap 當中間步）、`object_colormap`、`local_rule`、`x_vrule`；給了就只開列出的 | 全開 |
| `max_nodes` | 節點預算（主預算，可重現） | 2000000 |
| `max_depth` | 最大步數 | 4 |
| `budget` | 秒數上限（保險，正常用不到） | 60 |
| `max_solutions` | 最多收幾個 train 全對的程式 | 200 |
| `gate` | 守門參數：`support_alone`（4）、`support_after`（16）、`max_len_penalized`（4）、`max_steps_before_learner`、`max_table_rows`、`min_votes`；設 0 或 -1 關掉 | 見括號 |

- 主線 r07 的「空樹」在 C++ 端＝`{"prims":[],"learners":[]}`（D-r7-6）。
- 輸出每行一筆（題 × 設定）：`config`、`task_id`、`train_fit`（有 train 全對的程式）、`answered`（守門後還有答案）、`test_correct`（top-1 對）、`oracle_correct`（任何一個候選對）、`n_solutions`、`gated`、`program`、`cost`、`votes`、`nodes`、`nodes_to_first`（第一個 train 全對程式出現時已走的節點數）、`depth`、`out_of_budget`、`seconds`；加 `--dump` 會多一欄 `solutions`（每個候選的程式、cost、votes、對錯）。
- 每個設定最後一行是總結：`summary: true`、`solved`、`train_fit`、`answered`、`wrong`、`oracle`、`nodes`（總節點）、`task_seconds`（逐題秒數加總）、`cache_hits`、`wall_seconds`（整批的牆鐘時間）、`threads`。
- top-1 規則跟 Python `vote.choose` 相同（learner 結尾的權重 0.5；`local_rule`／`x_vrule` 排最後；同 cost 比票數），差別是沒有 formula 的形狀提示。
- 快取：鍵＝binary 內容雜湊＋spec 雜湊＋設定 JSON＋題檔內容，一筆一個檔，可以多個行程共用。
- 結果可重現：節點預算下，1 執行緒和 6 執行緒的輸出逐行一致（秒數除外）。

## 數字

### 小集 20 題（training，`random.seed(7)` 抽 20 題，清單見下）

| 量法 | 解題 | 答錯 | 秒數 |
|---|---|---|---|
| r06 混合入口 `native/bin/solve`（逐題加總） | 9 | — | 146.6（Python 段 34.4、C++ 段 108.5） |
| arcbatch 25k 節點（不守門） | 7 | 0 | CPU 2.4（6 執行緒估牆鐘 0.4） |
| arcbatch 200k 節點（不守門） | 7 | 2 | CPU 14.8，牆鐘 3.6 |
| arcbatch 200k 節點（守門） | 6 | 0 | 牆鐘 3.4 |
| arcbatch 2M 節點（不守門） | 7 | 2 | CPU 112 |
| 第二次跑（快取） | 同上 | | 0.0003 |

- 題：11852cab 1a07d186 1caeab9d 1f85a75f 1fad071e 22eb0ac0 23581191 23b5c85d 3906de3d 484b58aa 53b68214 6d75e8bb 7b7f7511 85c4e7cd 8eb1be9a 9172f3a0 a78176bb b190f7f5 bdad9b1f d4469b4b。
- 解出的 7 題 `nodes_to_first` 都 ≤ 55k，所以小集上 25k～50k 節點就夠，再多只是在沒解的題上燒時間。
- 守門掉的 1 題 d4469b4b 是 C++ 單跑時 32 列的 local_rule 碰巧對；混合入口裡它由 Python 先解，不受影響。

### 全量 400 題（C++ 單跑，200k 節點，6 執行緒，跟 S3 的評測同時跑）

| split | 設定 | 解題 | 答錯 | oracle | 牆鐘 |
|---|---|---|---|---|---|
| training | 不守門 | 106 | 38 | 107 | 兩個設定合計 250 秒 |
| training | 守門 | 104 | 12 | 107 | |
| evaluation（只審計） | 不守門 | 45 | 15 | 47 | 兩個設定合計 432 秒 |
| evaluation（只審計） | 守門 | 45 | 5 | 47 | |

- training 守門掉的 2 題（794b24be、d4469b4b）在混合入口都是 Python 解的，混合入口不受影響。
- C++ 單跑 200k 節點 evaluation 就有 45/400（混合入口 56）。

## 支持度守門怎麼定的

- 料：r06 混合入口在 training 上 Python 沒解、輪到 native 的 249 題，用同一支入口另存全部驗過的候選（`hybrid.py` 的副本加 `NATIVE_DUMP_DIR`，在 scratchpad），241 題有存檔。
- r06 native 在這些題上 top-1 答對 18、答錯 26；**oracle 也是 18**——答錯的題沒有一題的候選裡有對的答案，所以只能「不答」，換不到對的答案。ARC 計分只看 top-1，不答跟答錯一樣是 0 分，所以守門不會加分，作用是讓「native 說它解了」變可信，元優化器的學習曲線也不會被假陽性灌水。
- 特徵：答錯的 top-1 幾乎都是「前面 2～3 步＋一張大表」。每列平均分到的 train 輸出格數（格數 ÷ 列數）分得很開：對的多步程式最少 23.6，錯的多步程式大多 < 15；一步就是表的對題（67a423a3）是 7.2。所以門檻定 4（表就是整個程式）／16（表前面還有步驟），16 落在 14.4～23.6 的空檔裡。
- **審計說明（照實記）**：第一版把 colormap、object_colormap 也一起守，training 結果是答錯 26→6、答對不掉；拿去 evaluation 審計時會掉 be03b35f（`keep_sel → overlay_cells → colormap`，3 列）。改成只守 `local_rule`／`x_vrule`（就是 r06 已經在 `PENALIZED` 裡的兩個；colormap 最多 10 列，格數 ÷ 列數量不出它的容量），training 答錯 26→9、答對不掉。**這個選擇是看過 evaluation 審計之後做的**，門檻數字沒有再動。evaluation 審計（25 題 native 會答的題）：答錯 7→2，答對 13→13。
- 實作：`native/hybrid.py` 的 `SUPPORT_MIN`、`unsupported()`（trace metadata 多一欄 `support_gated`），C++ batch 的 `Gate`（`support_alone`／`support_after`，預設同值）。

## 改了什麼

- `native/src/batch.{hpp,cpp}`（新）：批次模式、設定、守門、快取、輸出。`main.cpp` 加 `--batch` 分派；`arcbatch.sh` → `bin/arcbatch`。
- `search.{hpp,cpp}`：learner 開關、記錄第一個解出現時的節點數。
- `background.cpp`、`objects_props.cpp`：全域狀態改 `thread_local`（多執行緒才安全）；物件抽取快取鍵改成每格一個位元組。
- `Makefile`：`-O3 -march=native -ffp-contract=off -pthread`（`-ffp-contract=off` 保證 cost 加總跟 Python 一樣，不被 FMA 改掉）。
- `tests/native/test_arcbatch.py`（新）：批次解題與總結、1／3 執行緒輸出一致、macro 與快取、守門函式。
- 入口契約與 trace 格式沒變（metadata 只多一欄）。

## 代定

- S1c-1 批次只走 C++，不做 hybrid 批次（主線回信：只用在舊樹對照組與旋鈕實驗）。
- S1c-2 預設預算用節點數，秒數只當保險；守門預設開。
- S1c-3 守門只守 `local_rule`／`x_vrule`，門檻 4／16；選「只守這兩個」是看過 evaluation 審計後做的（見上）。
- S1c-4 沒做 CUDA：小集上的瓶頸是沒解的題燒滿節點，降預算就解決；單題搜尋是深度優先、分支不規則，搬 GPU 不划算。
