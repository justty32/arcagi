# N4g：GPU 補位擴大來源（今晚全部 GPU 輸出 → `ARCAGI_GPU_FALLBACK` 重放）

前情：[N4f](README.md)。快照時間 **2026-11-10T02:05:39+08:00**（filler、phase-B、GP pass-1、GP sweep 都還在寫）。
重放方式與 N4f 相同：存檔 trace（training=gated-r07、evaluation=gated-r08）重跑 `gated.gate`，再接 `gated.gpu_fallback`（R1 門＝table+unseen）。沒改 gated.py、replay.py，也沒調門。

**更正 N4f 的前提**：`replay.py` 的 `SOURCES` 本來就有 phase-A、phase-B、filler train/eval d6 四個檔，不是只有 phase-A。下面 (i) 用 phase-A 單獨重放，結果和 N4f 的 149/58 完全一樣，所以 N4f 當時多出來的效果全部來自 phase-A。

## 1. 來源盤點（快照）

格式欄：「gpusearch」表示 `best.program`／`samples` 格式，`load_gpu_programs` 可以直接讀；「GP」表示 GP 輸出，解出的題有 `best.program`，沒解出的題只有 `partial`，載入器本來就會忽略 `partial`。兩種格式都不用轉換。

| 來源 | 格式 | 列數 | training／evaluation 題數 | 有程式的題（train／eval） |
|---|---|---|---|---|
| native-cuda overnight/phase-A | gpusearch d5 | 800 | 400／400 | 56／17 |
| native-cuda overnight/phase-B（寫入中） | gpusearch d6 | 41 | 41／0 | 1／0 |
| native-cuda filler/train-open-d6（寫入中） | gpusearch d6 | 81 | 81／0 | 5／0 |
| native-cuda filler/eval-open-d6（寫入中） | gpusearch d6 | 81 | 0／81 | 0／0 |
| gpu-gp overnight/pass-1（寫入中） | GP | 543 | 253／290 | 8／3 |
| gpu-gp ho/on40-{orig,ho,mdl} | GP | 41×3 | 41／0 | 8、4、4／0 |
| gpu-gp ho/real-{ho,mdl} | GP | 40×2 | 20／20 | 1、0／0 |
| gpu-gp ho/sweep/*（6 檔，寫入中） | GP | 11–41 | on40 只有 train；real 是 20／20 | 0–6／0 |
| gpu-gp bench/real/{gp,random,exhaustive} | GP／gpusearch | 40×3 | 20／20 | 1、0、0／0 |

**跳過的檔**：
- `gpu-gp-1109/bench/synth-L*`、`gpu-gp-1109/synth/L*/planted`：合成題，題號不在 ARC 的兩個 split 裡。
- `*-verify.jsonl`：驗證摘要，不是搜尋輸出。
- `task-features-1109/profile/*-d5.jsonl`：profile 格式，`best` 是分數不是程式。

快照和合併輸入放在 scratchpad `n4g/snap/`（不 commit）。快照時如果某行寫到一半，會丟掉那一行，這次沒有遇到截斷。

## 2. 重放結果

| 設定 | split | 關閉 | 開啟 | 新增對題 | 新增假解 | 衝突 | 觸發 |
|---|---|---|---|---|---|---|---|
| (i) 只用 phase-A | training | 147 | **149** | 46f33fce、a79310a0 | 25d8a9c8 | 0 | 3 |
| (i) 只用 phase-A | evaluation（審計） | 56 | **58** | 66e6c45b、be03b35f | 0 | 0 | 2 |
| (ii) 19 檔合併 | training | 147 | **149** | 同 (i) | 25d8a9c8、**1fad071e、f8ff0b80** | 0 | 5 |
| (ii) 19 檔合併 | evaluation（審計） | 56 | **58** | 同 (i) | **8597cfd7** | 0 | 3 |

兩種設定的「關閉」結果都和存檔逐題一致（差異 0）。原始輸出：[n4g/A-training.out.txt](n4g/A-training.out.txt)、[n4g/A-evaluation.out.txt](n4g/A-evaluation.out.txt)、[n4g/ALL-training.out.txt](n4g/ALL-training.out.txt)、[n4g/ALL-evaluation.out.txt](n4g/ALL-evaluation.out.txt)。逐來源歸因：[n4g/attrib.txt](n4g/attrib.txt)。

**擴大來源後沒有多對任何一題**，只多了 3 題假解。

## 3. 假解判讀

- 補位的假解比例：training 從 1/3 升到 3/5，evaluation 從 0/2 升到 1/3。比例明顯變差。
- 歸因：新增的 3 題假解全部來自 GP 來源（pass-1、on40-orig、real-ho、sweep、bench/real/gp）。phase-B 和 filler 這些 gpusearch 檔沒有多觸發任何題。
- 3 個假程式的共同點：長度 8–9 步，有重複或抵消的運算（連續兩次 `downscale`、多層 `split_overlay` 疊在一起、`colormap` 寫死好幾個顏色），一看就是在 train 上湊出來的。例如 1fad071e：`downscale×2, tile, colormap, crop_bbox, gravity, split_overlay, colormap`。gpusearch 是在完整深度下窮舉，給的是最短程式；GP 沒有最短的保證。
- **結論**：R1（table+unseen）擋 gpusearch 來源還可以（還是有 25d8a9c8 這 1 題漏網），擋 GP 來源不夠。

**建議**（沒有在 evaluation 上調門；要調只能用 training 或 holdout 決定）：
1. 最簡單：補位只吃 gpusearch 窮舉輸出，GP 輸出先不接。以這次快照來說，這樣做 0 損失，而且少 3 題假解。
2. 如果要接 GP，加一道「最短／不冗餘」門。做法是用 CPU 的 gpusearch，在 GP 程式長度減 1 以內重新窮舉，或檢查程式能不能刪掉某一步還照樣過 train；刪得掉就拒收。另一個選項是長度上限 ≤6。
3. 針對 25d8a9c8 這類，加「colormap 寫死顏色」的門：colormap 映射的顏色如果沒在 test 輸入裡出現，或是要靠 ≥4 組映射才湊得出來，就拒收。這要在 training 上定門檻。

## 4. 06:00 後再重放

```
S=/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n4g
reports/gpu-fallback-1110/n4g/snapshot.sh $S/snap-0600
systemd-run --user --scope --unit=arcagi-n4g-replay2 -p MemoryMax=12G nice -n 19 \
  reports/gpu-fallback-1110/n4g/run.sh $S/snap-0600 $S/out-0600
cat $S/out-0600/*.out.txt
```

跑完四組大約 1 分鐘。如果要排除 GP 來源（建議 1），把 run.sh 的 `ALL` 改成只列 `nc-*.jsonl`，或直接設 `N4G_SOURCES` 呼叫 `n4g/replay_sources.py`。
