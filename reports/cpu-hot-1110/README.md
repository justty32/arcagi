# N8：seed CPU hot paths

已建置 `native/bin/arcbatch-hot-a`（A）與 `native/bin/arcbatch-hot`（A+B）。
Makefile 僅追加目標，`native/src/` 與既有 binary 均未修改；所有新 object 分別在
`native/hot/obj-a/`、`native/hot/obj-ab/`。編譯使用既有 CXXFLAGS，最多 `-j4`。

## 實作

A 在 `native/hot/seed_value.cpp` 的 `call()` 使用 thread_local direct-mapped cache：
4096 entries、每個 worker 256 KiB，完整比對 generation、lambda handle、input、arity、
兩個 64-bit arguments。命中會扣除原呼叫的步數，預算不足時回到真實 eval。
只插入成功、剩餘步數非負、且 Store entry 數量不變的結果；不快取 ERR。
`ARC_HOT_STATS=1` 會在 worker 結束時把 counters 寫到 stderr，預設關閉。

Generation 在 Store reset 與每次 compile（含失敗）更新。已檢查目前所有 Arena reset
均緊接 Store reset；所有 node 建立都經過 compile。這也涵蓋 `seed_enum.cpp` 與
`seed_decomp.cpp` 暫時縮回 Arena 後，下一次 compile 重用 node id 的情況。
採較保守的失效策略：追加新 node 時也使舊 cache 失效。

B 在 `native/hot/seed_enum.cpp` 讓兩種 choose 共用 append-only Subst，離開分支時以
RAII 還原 binding 數量（含 unify 失敗與例外）；保留原 unify、resolve 與拜訪順序。
Enumerator 重用 Pick vector，BodyPool 每層重用 chosen vector；lambda 參數只在 pool
miss 時複製，且先複製再呼叫可能使 Types vector 重新配置的 probes。
eval_prim 把每個候選固定的 value offset／lambda node 移到 example loop 之前取得。

## 已執行驗證

公開 training 前 100 題、seed、decomp、4 threads、budget 1e6，每個 binary 跑一次。
[比較結果](cmp-1e6.txt)：A 與 A+B 均 **0/100 mismatch**；逐題所有欄位只排除 seconds，
保留 eval_steps、near 順序與 JSON 型別。三者同為 train_ok 7、test_ok 5、errors 0，
合計 nodes 92,571,392。

| binary | 單跑 wall 秒 | 起始 loadavg1 |
|---|---:|---:|
| arcbatch | 11.318109 | 13.35 |
| arcbatch-hot-a | 11.667099 | 13.58 |
| arcbatch-hot | 10.002692 | 14.16 |

這是功能驗證時的單跑紀錄，不能視為正式 benchmark。A 開啟 counters，A 與 A+B 執行期間
另有 pytest 負載；機器也有其他夜跑。正式速度與 B 是否超過 2% 留給 lead 的交錯三輪量測。
[A counters](hit-rate.json)：767,259,102 / 892,511,137 calls 命中，**85.9663%**，
此批 budget fallback 0 次。

[完整 native pytest](pytest.txt)：**24 passed、7 failed，23.09 秒**。7 個失敗均為既有
GPU 測試：sandbox 內 CUDA 回報 `no CUDA-capable device is detected`，或 GPU fallback 後
layers_gpu／verified 為 0。未修改既有測試、GPU 原始碼或設定；完整測試綠燈仍待可存取
CUDA 的環境驗證。[排除四個 GPU 測試模組的 CPU 驗證](pytest-cpu.txt)：**21 passed，22.06 秒**，
包含新增的兩個 hot parity cases（decomp false／true）。

[cache_check.cpp](cache_check.cpp)／[結果](cache-check.txt) 另驗證精確步數扣除、預算剛好為零、
預算不足回退、input 與第二參數 key、Arena node id 重用、Store id 重用，以及新 list
建立後才能快取既有 list。cmp 自檢確認 seconds 差異通過、eval_steps／near 順序差異拒絕，
並拒絕空輸出。`bash -n bench.sh` 通過；analyze 已以本次單跑資料驗證。

systemd user bus 被 sandbox 拒絕（Operation not permitted），未繞過限制。此次所有建置、
評測與 pytest 程序均加 55 秒 timeout，實際皆在一分鐘內完成。

## 給 lead 執行

未執行 1e7 或重複計時。從 repo root 執行：

```sh
make -C native hot -j4
bash reports/cpu-hot-1110/bench.sh reports/cpu-hot-1110/bench-lead
python3 reports/cpu-hot-1110/analyze.py reports/cpu-hot-1110/bench-lead
```

bench.sh 使用 systemd user scope、MemoryMax=16G、nice 19，依 1e6 再 1e7、每輪
arcbatch → hot-a → hot，重複三輪，固定 4 threads。它會關閉 cache counters，記錄
`wall.txt`（B bin rep seconds loadavg1），將每個 hot run 與同 budget 的 baseline rep1
比較後附加到 `cmp.txt`，最後 touch DONE；需要全新的 OUTDIR。
啟動前與執行期間均監看 `~/arcagi-STOP`，中止時不寫 DONE，只終止自己啟動的子程序。
預設 inputs 在指定 n8 scratchpad；移動 inputs 時可設定 `ARC_HOT_DATA`。

本次原始 JSONL 位於
`/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n8/verify/`。
未 commit、未 push；報告只保存小型紀錄與腳本。

## Interleaved bench (lead, 11-10 ~02:00, training first 100, --mode seed, decomp, 4 threads, x3 interleaved, nice 19)

| budget | bin | wall median (min..max), s | speedup | mismatches |
|---:|---|---:|---:|---:|
| 1000000 | arcbatch | 10.367 (9.366..10.418) | 1.000x | reference |
| 1000000 | arcbatch-hot-a | 9.722 (8.616..9.817) | 1.066x | 0 |
| 1000000 | arcbatch-hot | 9.317 (9.066..9.667) | 1.113x | 0 |
| 10000000 | arcbatch | 136.086 (117.042..141.460) | 1.000x | reference |
| 10000000 | arcbatch-hot-a | 132.607 (113.594..143.312) | 1.026x | 0 |
| 10000000 | arcbatch-hot | 118.498 (105.139..124.502) | 1.148x | 0 |

Observed loadavg1 at run start: 9.39..15.52.

Per-change gain (median): A alone 1e6 +6.6% / 1e7 +2.6% (within noise; range overlaps); B on top of A: 1e6 +4.4%, 1e7 +11.9%. A+B total 1.11x (1e6), 1.15x (1e7). Load avg 9.4..15.5 from other night runs, so spreads are wide (1e7 arcbatch 117..141 s). All 12 hot runs: 0/100 mismatched rows vs arcbatch r1 (keys incl. eval_steps, near); raw: bench-wall.txt, bench-cmp.txt.
