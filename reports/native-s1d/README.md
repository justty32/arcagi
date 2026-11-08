支線 S1 第四任的報告：只用 training 重選支持度門（D-r7-18），以及 arcbatch 的空樹語言模式（seed）。

← 上一任 [native-s1c](../native-s1c/README.md)｜交棒 [交棒.md](交棒.md)

## 1. 支持度門重選（D-r7-18，只用 training）

### 選法（看結果前寫死在 `native/tools/gate_select.py`）

- 料：training 400 題。arcbatch 200k 節點，關掉支持度門，用 `--dump` 存下每個過 train 的候選，連同 test 命中和輸出鍵；S5 合成 pair 只當第二標籤，不進搜尋。
- 重播：離線照 `batch.cpp` 的 top-1 規則重選（penalized、cost、票數、順序），掃三個維度：
  - 守哪些 learner：colormap、object_colormap、local_rule、x_vrule 的全部子集
  - support_alone：0～16
  - support_after：0～48
- 母體 P：r06 混合入口在 training 上輪到 native 答的 249 題（trace 的 `source != python`），因為門只在這些題上起作用。
- 規則：
  1. 可行＝P 上的誤擋為 0（不守門時 top-1 答對、守門後不再答對的題，要一題都沒有）。
  2. 可行的設定裡取答錯最少的。
  3. 平手時取守的種類少的，再取門檻小的。
- 重跑方法：

```
python native/tools/gate_select.py prepare --out DIR
nice -n 19 systemd-run --user --scope -p MemoryMax=8G native/bin/arcbatch \
    --tasks DIR/list.txt --configs DIR/configs.jsonl --threads 6 --dump --out DIR/dump.jsonl
python native/tools/gate_select.py select --dump DIR/dump.jsonl
```

（arcbatch 牆鐘 95 秒，6 執行緒。）

### 結果

| 設定 | P 答對 | P 答錯 | P 誤擋 | P 合成 pair 過半錯 | 400 題答對 | 400 題答錯 |
|---|---|---|---|---|---|---|
| 不守門 | 15 | 16 | — | 27 | 106 | 38 |
| ee869e5（守 local_rule／x_vrule，4／16） | 15 | 5 | 0 | 16 | 104 | 12 |
| **重選：守 colormap＋local_rule＋x_vrule，alone 0、after 16** | 15 | **3** | 0 | 14 | 103 | 7 |

- **training 獨立重選得到的不是同一設定**。差別有兩處：
  - colormap 也要守。這正是第三任第一版的做法，後來看過 evaluation 才拿掉。
  - 表就是整個程式時不守（alone 從 4 改成 0）。
- 400 題全量上，重選版比不守門少答對 3 題（445eab21、794b24be、d4469b4b）。這三題都不在 P 裡：混合入口由 Python 先解，所以入口不受影響。
- 平手的設定有 24 個，守的種類都是 {colormap, local_rule, x_vrule}，或再加 object_colormap。
- 已套用：`native/hybrid.py` 的 `SUPPORT_MIN=(0.0, 16.0)`，`GUARDED` 加入 colormap；`batch.cpp` 的 Gate 預設值同步。evaluation 沒看，也不回頭調。
