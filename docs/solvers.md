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
