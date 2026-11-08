# 接上自己的求解器

方法不限：規則搜尋、程式合成、邏輯推理或手寫解法都能接到同一個測試介面。內建 `identity` 只是把 test input 原樣送回，用來確認評測流程，不是有競爭力的解法。

## Python plugin

在專案根目錄建立 `my_solver.py`：

```python
from arcagi.tasks import Grid, SolverTask


def solve(task: SolverTask) -> list[Grid]:
    # Infer a rule from task.train; this example only copies test inputs.
    return list(task.test)
```

```sh
uv run arcagi solve data/ARC-AGI/data/training/007bbfb7.json --solver my_solver:solve --output artifacts/predictions.json
uv run arcagi eval --split training --solver my_solver:solve --output artifacts/training-score.json
uv run arcagi eval --split evaluation --solver my_solver:solve --output artifacts/evaluation-score.json
```

`SolverTask.task_id` 是題目 ID，`train` 是範例 tuple，每個範例有 `.input` 與 `.output`；`test` 只有輸入網格 tuple，不含標準答案。`Grid` 使用不可變的 tuple of tuples；求解器可以回傳 list 或 tuple 形式的網格。回傳順序必須與 test 相同，數量必須完全一致，每個 test 只有一個預測。

介面不把 test 答案傳給 plugin，但 plugin 是本機 Python 程式，仍能存取本機檔案；這不是防作弊沙箱。求解器應只使用傳入的示範和 test input 推導規則。HTML 瀏覽器及詳細評測報告包含答案，請避免讓解題流程讀取它們。

### 回報嘗試軌跡與範本

想保留「試了哪些假設、對訓練範例的驗證結果、最後選哪個」，回傳 `SolverResult(predictions, trace)`；格式見 [嘗試軌跡](traces.md)。[src/arcagi/solvers/template.py](../src/arcagi/solvers/template.py) 是可複製的骨架：試幾個整張網格的對稱變換、用 `check_on_train` 驗證、用 `TraceRecorder` 記錄，本身不是正式解法（training 解出 6/400、evaluation 0/400）。第一輪正式解法是 [search.py](../src/arcagi/solvers/search.py)（`arcagi.solvers.search:solve`，網格 DSL＋枚舉，evaluation 21/400、training 57/400，見 [reports/dsl-search-r01](../reports/dsl-search-r01/README.md)）。

```sh
uv run arcagi eval --split training --solver arcagi.solvers.template:solve --name template \
  --output artifacts/template.json --traces artifacts/template-traces.jsonl
```

`--name` 設定報告中的方法名稱，比較時用得到。

## 外部程式直接跑整份評測

任何語言的程式只要遵守 [檔案介面](experiments/protocol.md)（讀 request JSON、寫 response JSON，可選寫軌跡），就能直接跑完整 split：

```sh
uv run arcagi eval --split evaluation --name sh-identity \
  --external "sh examples/sh_identity.sh {input} {output} {trace}" \
  --output artifacts/sh-identity.json --traces artifacts/sh-identity-traces.jsonl
```

`--external` 字串依 shell 規則切成 argv，但**不經 shell 執行**（不能用 `&&`、重導向）。每題預設 60 秒，可用 `--timeout` 改；`--params '{"budget": 5}'`、`--seed 1` 會放進 request；`--cwd` 指定工作目錄。每題的 request／response／log／trace 存在 `--artifacts DIR`，未指定時放在 `<output 檔名>-runs/`。範例：[sh_identity.sh](../examples/sh_identity.sh)（POSIX sh）、[c_identity/solver.c](../examples/c_identity/solver.c)（C99，`cc -std=c99 -O2 -o examples/c_identity/solver examples/c_identity/solver.c` 後用 `--external "examples/c_identity/solver {input} {output} {trace}"`）。`solve` 也接受同一組參數，方便單題除錯。

## 比較方法與逐題對錯

`compare` 讀兩份以上的 `eval` 報告或 experiment 結果（`results.json` 或其輸出目錄），第一份當基線：

```sh
uv run arcagi compare artifacts/identity.json artifacts/template.json --format markdown
uv run arcagi compare base=artifacts/identity.json new=artifacts/template.json \
  --labels my-labels.csv --label-column family \
  --output artifacts/compare.json --matrix-csv artifacts/compare-matrix.csv
```

方法名稱取報告內的 solver 名稱；同名時用 `NAME=PATH` 指定。experiment 結果內每個 solver 各成一個方法（帶 `NAME=` 時命名為 `NAME/solver`）。一題有多次 run（seeds × repeats）時，**每次都對**才算解出；矩陣 CSV 單次顯示 `1`／`0`、多次顯示 `k/n`，沒跑的題留空。

輸出包含各方法解出數；每一對方法的共同題數、都解出、都沒解出、只有 A／只有 B 解出的題號；相對基線的 `newly_solved`（新增解出）與 `regressed`（退步）。`--format markdown` 另列出方法間結果不同的題。

**題型標籤**：`--labels` 吃任意 task_id → category 對照檔。CSV 需有 `task_id` 欄（`.json` 副檔名會去掉），類別欄用 `--label-column` 指定、預設取第一個其他欄；同一題可多列，或用 `--label-sep '|'` 把一格拆成多類。JSON 則是 `{"task_id": "類別" 或 ["類別", ...]}`。沒出現在對照檔的題歸 `(unlabeled)`；一題可屬多類，各類題數會重疊、不能相加。

## 非 Python 解法與手工答案

要自動反覆執行其他語言、多方法或參數組比較，使用 [experiment 檔案介面](experiments.md)；框架負責寫 request、啟動命令、讀 response、逾時和保存圖表／JSON／CSV。下列 `score` 則適合已有預測檔案的情況。

任何程式只要寫出 JSON 就能評分。JSON 最外層以 task ID 為鍵，值是依 test 順序排列的預測網格清單，例如某題有兩個 test：

```json
{"example": [[[1, 2], [3, 4]], [[5]]]}
```

```sh
uv run arcagi score --tasks-dir path/to/tasks --predictions path/to/predictions.json --output artifacts/score.json
```

`solve --output` 也產生同樣的格式，可直接交給 `score`。評分選取的題目 ID 必須與檔案相符；未選取的多餘 ID 會被拒絕，缺少的題目或不合法的答案會計為錯誤，仍保留在總題數中。

求解器錯誤、回傳數量不符或非法網格都會記在報告內，該題算未解出，不會默默跳過。`solve` 與 `eval` 可加 `--timeout 10`，以每題獨立 Python 程序限制 10 秒；時間包含程序啟動與 plugin 匯入，各題不共享 plugin 狀態。逾時記為失敗，評測會繼續下一題。未指定時不限制時間。這個機制不是安全沙箱，也不負責終止 plugin 額外建立的子程序；搜尋演算法仍應設定自己的預算。
