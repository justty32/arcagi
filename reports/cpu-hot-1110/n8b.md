# N8b：A+B profile、完整結果 cache、結果緩衝區

已建立 `arcbatch-hot-prof`、`arcbatch-hot-c` 與 `arcbatch-hot-d`。
三者在公開 training 前 100 題、seed、decomp、budget 1e6、4 threads 上，
相對 `arcbatch` 均為 **0/100 mismatches**，比較只排除 seconds，包含 eval_steps、
near 順序及 JSON 型別。C 尚未顯示加速；D 單跑比 A+B 快約 2.6%，仍須正式交錯量測。
未執行 1e7、正式 benchmark 或 commit。

先對 A+B 做一次 1e6 profile，表格原檔為 [n8b-prof-1e6.txt](n8b-prof-1e6.txt)。
外部 wall 12.816573 秒、起始 loadavg1 5.61；binary 內 wall 12.804800 秒。
以下為 exclusive rdtsc 的 worker 經過時間，含排程等待與 profiler 本身成本，
不是硬體 CPU cycles，也不宜拿 prof wall 當速度基準。

| bucket | 秒 | % | calls |
|---|---:|---:|---:|
| first_order_eval | 15.148714 | 29.852 | 689835290 |
| ho_lambda_body | 9.532957 | 18.786 | 892511137 |
| ho_result_build | 5.083620 | 10.018 | 646024227 |
| ho_loop_rest | 12.104995 | 23.854 | 74010803 |
| lambda_body_pool | 1.172990 | 2.312 | 1559859 |
| choose_unify | 1.873522 | 3.692 | 1253 |
| offer | 2.766396 | 5.452 | 87099732 |
| dedup_seen_insert | 1.916479 | 3.777 | 89528102 |
| cond_witness | 0.178485 | 0.352 | 1072 |
| other | 0.967320 | 1.906 | 1253 |
| total | 50.745477 | 100.000 | — |

計時以巢狀 scope 切換，內層時間從外層扣除。HO body 包含 `call()` 的 A cache、
eval 與 body 的 first-order primitive；巢狀 HO 再拆成同一組 HO buckets。
HO build 包含結果 append、scratch 建立／釋放與 Store::make；loop rest 包含其餘迴圈工作。
FO 也計入 BodyPool 的 first-order eval；各 bucket 均為互斥時間。
calls 是各 instrumentation scope 的進入數：choose_unify／other 每個 run_enum 各一次，
不是遞迴 choose 次數；HO build 每個 append、scratch lifetime 邊界與 Store::make 各計一次。
other 主要是 run_enum 建構、收尾、排序與析構；未完整計時的載入、decomp orchestration
與 I/O 不在此總和。`ARC_HOT_PROF` 未設定時關閉計時；設為路徑寫表，設為 `-` 寫 stderr。
只有 prof binary 含這些 instrumentation。

HO 三項合計 **52.658%**，因此先選 C，並以 D 處理其中的結果建構與 append。
未改 dedup：目前本來就是 flat open addressing，且只占約 3.8%。

C（`HOT_C`）是 A+B 上的完整 MAP/FILTER/ZIPWITH/FOLD 結果 cache，
65536 個 direct-mapped entries、每 worker 約 4 MiB。完整比對 generation、primitive、
lambda handle、input 與所有 argument handles；primitive 同時決定 arity。
只快取成功且剩餘步數非負的呼叫，命中扣回完整 eval cost；預算不足走原本 eval，
保留失敗位置與部分 Store 寫入。沿用 A 的 Store reset／每次 compile（含失敗）generation。
初版 4096 entries 的診斷命中率約 18%，擴大仍只有約 20%；長度統計顯示約一半呼叫
少於 8 個元素。因此最終 C 對長度小於 8 的迴圈直接走原路，避免昂貴的 key 查詢。
診斷可用 `ARC_HOT_STATS=1`，正式 bench 會關閉 counters。

已特別檢查「第一遍可新增 Store entries，重播卻沒有遺失副作用」：成功的 deterministic
呼叫已 intern 全部 intermediate／result lists；同 generation 重算只找回既有 entries。
`tests/native/hot_c_check.cpp` 也連結**未啟用 C 的 A+B object**，在完整呼叫後重算，
assert Store 的 elems、off、len、boolish、hashes、table 與 used 均未變。
再逐次比較 A+B、C、D 的結果、精確剩餘步數與整份 Store state hash，包含不足預算時的
部分 list 建立。測試涵蓋不同 input／primitive／第二清單／初始 accumulator、bool/int、
零成本 body、負預算、ERR、巢狀呼叫、Arena ID 重用、失敗 compile 及 Store ID 重用。

D（`HOT_D`）獨立建立於 A+B，不包含 C，以便隔離量測。MAP/FILTER/ZIPWITH
使用八層 thread-local 結果 arena，保留每層曾用到的最大容量，按 index 寫入，
不逐元素 push_back，也不重複初始化已配置區域。超過八層使用 RAII 獨立陣列；
仍呼叫原本的 Store::make，不改 intern 順序或 eval 次數。
已測超過八層巢狀、2048 元素、空結果、短結果及中途 ERR 後重用。

最終版本各跑一次 1e6 的功能驗證如下，**不是正式 benchmark**。
各次主機負載不同，A+B 計時期間另有短 pytest，因此不能據此認定穩定加速。

| binary | wall 秒 | 起始 loadavg1 | mismatches vs arcbatch |
|---|---:|---:|---:|
| arcbatch | 9.968777 | 11.61 | reference |
| arcbatch-hot | 9.615991 | 12.00 | 0/100 |
| arcbatch-hot-c | 10.004753 | 12.27 | 0/100 |
| arcbatch-hot-d | 9.370234 | 11.71 | 0/100 |

四者同為 train_ok 7、test_ok 5、errors 0、nodes 合計 92,571,392。
prof 的同一批 1e6 rows 亦經 cmp.py 對原 A+B 與最終 arcbatch 比較，均 0/100 mismatches。
最終 C 單跑約為 baseline 的 0.996x，D 約 1.064x；這些數字只說明仍需交錯 bench，
不把 C 當成已成立的速度改進。

`uv run pytest -q tests/native/test_arcbatch_hot.py`：**8 passed**；包含 C、D 各兩個
decomp parity cases，以及各一個 interpreter／budget／Store invariants case。
相關 Python 的 Ruff check／format、shell syntax、舊 analyze 輸出逐 byte 比對與新 bins
的 analyze 讀取均通過。未跑 GPU 測試。
未定義 HOT_C／HOT_D 時，A 與 A+B 的 evaluator 預處理結果各自與 HEAD 原檔逐 byte 相同；
prof 在後續生成後的預處理結果也與量測當時相同。
native/src 未修改，Makefile 只追加 targets；舊 hot targets 不定義任何新 macro。

建置：

```sh
timeout 55 nice -n 19 make -C native hot hot-prof hot2 -j4
```

lead 從 repo root 執行以下兩項；scripts 自動包在 systemd **user scope**、MemoryMax=16G、
nice 19，固定四個 CPU threads，並在開始與執行期間監看 `~/arcagi-STOP`。
`ARC_HOT_DATA` 可改 inputs 目錄，預設沿用 n8 的 train100.txt／cfg-<budget>.jsonl。

```sh
scratch=/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n8b
bash reports/cpu-hot-1110/n8b_prof.sh 10000000 "$scratch/prof-1e7-lead"
bash reports/cpu-hot-1110/n8b_bench.sh "$scratch/bench-lead"
python3 reports/cpu-hot-1110/analyze.py "$scratch/bench-lead"
```

prof 的表格是 OUTDIR/profile.txt；兩個 scripts 都要求新 OUTDIR，成功完成才寫 DONE。
bench 先 1e6 再 1e7，依 arcbatch → hot → hot-c → hot-d 交錯三輪；每次 hot／C／D
輸出均與同 budget 的 arcbatch r1 以 cmp.py 比較，寫入 cmp.txt。
analyze.py 保留舊 bins 的輸出與順序，並自動列出新增 binaries。

本 sandbox 的 systemd user bus 回報 Operation not permitted，已依 brief 備援規則，
本次所有建置、評測與 pytest 程序均加 55 秒 timeout，編譯最多 -j4。
1e7 與 n8b_bench.sh 均未執行。raw JSONL／診斷與驗證資料只在上述 n8b scratchpad，
主要為 profile-1e6/、final-verify/；探索用 counters 在 cache-stats/、cache-64k/、cache-lengths/。

變更檔案：native/Makefile；native/hot/seed_value.cpp、higher_cache.hpp、result_buffer.hpp；
native/hot/prof/{generate.py,prof.hpp,main.cpp,seed_enum.cpp,seed_value.cpp}（末兩者為生成檔）；
tests/native/{test_arcbatch_hot.py,hot_c_check.cpp}；本報告、n8b-prof-1e6.txt、
n8b_prof.sh、n8b_bench.sh、run_one.py 與 analyze.py。object／binary 為建置產物，未 commit。

## 1e7 profile (lead, 11-10 ~02:40, arcbatch-hot-prof, 4 threads, nice 19; raw [n8b-prof-1e7.txt](n8b-prof-1e7.txt))

| bucket | s | % | calls |
|---|---:|---:|---:|
| first_order_eval | 280.9 | 28.35 | 6.25e9 |
| ho_lambda_body | 231.6 | 23.38 | 1.38e10 |
| ho_result_build | 100.0 | 10.09 | 9.59e9 |
| ho_loop_rest | 245.0 | 24.73 | 1.07e9 |
| lambda_body_pool | 7.5 | 0.75 | 1.9e7 |
| choose_unify | 30.2 | 3.05 | — |
| offer | 45.4 | 4.58 | 8.4e8 |
| dedup_seen_insert | 35.5 | 3.58 | 8.5e8 |
| cond_witness / other | 14.8 | 1.50 | — |
| total | 990.8 | 100 | |

HO (map/filter/zipwith/fold) total 58.2% at 1e7 (52.7% at 1e6) — still the largest hotspot; first-order eval 28.3%.
Interleaved bench (arcbatch / hot / hot-c / hot-d x3) still running; see n8b-progress.md.
