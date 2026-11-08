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

## 2. 空樹語言模式（arcbatch --mode seed／seed-run／seed-sub）

C++ 移植 `src/arcagi/seed/`，原始碼在 `native/src/seed_*.{hpp,cpp}`：值、型別、32 個原語、直譯器、Enumerator、BodyPool、cond_witness，另外照 r07 DEFAULT_SPLITS 移植了 decomp／witness 七個拆法（可選）。以 Python 為真值。介面跟 [05-S1介面規格](../../notes/rounds/r08/05-S1介面規格.md) 對齊，跟規格不同的地方列在 §2.4。

### 2.1 用法

```
native/bin/arcbatch --mode seed (--taskset FILE [--split learn,holdout] | --tasks LIST | --task FILE ...)
    [--ids a,b,c] [--data-dir DIR] [--configs CONFIGS.jsonl] [--threads 6] [--out OUT.jsonl]
native/bin/arcbatch --mode seed-run --programs JOBS.jsonl [--threads 6] [--out OUT.jsonl]
native/bin/arcbatch --mode seed-sub --subproblems SUBS.jsonl [--threads 6] [--out OUT.jsonl]
```

- `--taskset` 不給 `--split` 就收所有是 list 的欄位；`--ids` 只留指定的題，用來取 CRN 子集；`--data-dir` 預設 `<repo>/data/ARC-AGI/data/training`。
- 設定檔每行一個：`{"name", "lib": "blocks.json", "budget": 100000, "decomp": false | true | ["map", ...], "lam_depth": 2, "exclude": ["transpose"], "order": {"名": 權重}}`。
  - `decomp`：`false` 等於 `seed.enum.solve(..., decompose=False)`；`true` 是 r07 的七個拆法；名單只能用這七個名字，給 `halves`、`nest` 會回錯，訊息叫你改用 seed-sub。
  - `exclude` 只在搜尋時生效；train_ok／test_ok 的重驗用全部原語，跟 grow 的 `solve_task` 一樣。
- 輸出（每題 × 設定一行）：`task_id, config, program, train_ok, test_ok, nodes, nodes_to_first, seconds, near, eval_steps[, error]`；每個設定最後一行是 summary（`solved, train_ok, errors, nodes, task_seconds, wall_seconds`）。
  - `eval_steps` 是 C++ 實際執行的原語呼叫數，包括 HOF 裡 lambda body 的步數，所以跟 Python 的近似值不同，不拿來比對。
- seed-run：每行 `{"id", "program", "inputs": [...], "lib"?, "exclude"?}`，回傳 `{"id", "values": [值或 "ERR", ...]}`；規格 §8 的單一 `input` 也吃，回傳多一欄 `value`。
- seed-sub：照規格 §7，`examples`、`extra[].leaf`、`lam_body_max`、`cond_limit` 都吃。另外多收兩種寫法：
  - `cond_budget`：等於 Python `_direct` 的 budget，limit＝cond_budget − nodes。
  - `xs`／`outs` 分開給。
  - 輸出 `{"id", "program", "nodes", "nodes_to_first", "near", "cond": {"program", "used"}, "eval_steps", "seconds"}`。
