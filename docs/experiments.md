# 跨語言實驗與比較

`experiment` 以 JSON 檔案和外部程序連接解法。只要能讀寫 JSON，Python、C++、Rust、JavaScript 或其他語言都用同一份題目、seed、重複次數及計分規則；不需要匯入本專案的 Python 套件。

```sh
uv run arcagi experiment examples/experiment.json --output artifacts/experiment-demo
uv run arcagi experiment examples/experiment.json --task 007bbfb7 --output artifacts/one-task
uv run arcagi experiment examples/experiment.json --tag fill --output artifacts/fill-tasks
```

用瀏覽器開 `artifacts/experiment-demo/report.html` 看圖表及比較表。範例執行兩種流程基線，分別原樣輸出輸入、輸出同尺寸全零網格；它們只示範介面。

## 定義方法與題型

完整可執行設定見 [examples/experiment.json](../examples/experiment.json)。最小設定如下；`path` 與 `cwd` 都相對於設定檔所在目錄，將下列內容放在 `examples/` 才能直接使用這些路徑：

```json
{
  "version": 1,
  "tasks": [{"path": "../data/ARC-AGI/data/training/007bbfb7.json", "tags": ["scale"]}],
  "solvers": [{
    "name": "my-method",
    "command": ["python", "file_identity.py", "--input", "{input}", "--output", "{output}"],
    "params": {"mode": "identity"}, "cwd": "."
  }],
  "seeds": [0, 42], "repeats": 2, "timeout_seconds": 10
}
```

每種方法會跑相同的「選取題目 × seeds × repeats」。每次只提交每個 test 的一個預測；repeats 不是一次任務可猜多次的機會。不同參數組請使用不同的 solver `name`，方便分開比較。名稱限英數開頭，後面可接英數、底線、連字號及句點。

`tags` 是你自己的分類，不是官方題型。可讓一題有多個 tag，也可不分類。同種篩選器重複指定時取聯集，例如 `--tag fill --tag scale`；同時提供 `--task` 和 `--tag` 則取交集。未知 ID、未知 tag 或空集合會直接報錯。

## 檔案介面

每次執行建立獨立目錄，把 `{input}`、`{output}` 換成 request／response 的絕對路徑；也支援 `{task_id}` 與 `{seed}`。`command` 是 argv 陣列，直接啟動程序，不經 shell。可改成 `['node', 'solver.js', '{input}', '{output}']` 或 `['./solver', '{input}', '{output}']` 這類呼叫；JSON 設定檔內需使用雙引號。

輸入檔是下列 envelope；實際 `train` 含所有示範，`test` 只有 input，不含答案：

```json
{
  "schema_version": "arcagi-solver-input/1",
  "task_id": "example",
  "task": {
    "train": [{"input": [[1]], "output": [[2]]}],
    "test": [{"input": [[3]]}]
  },
  "seed": 42,
  "params": {"budget": 100}
}
```

解法讀取 `task`，依 test 原順序寫出 response：

```json
{"example": [[[4]]]}
```

response 必須恰好包含此次 task ID，且每個 test 恰有一個合法網格。解法自行解讀 `params`，也自行將 `seed` 套用到使用的亂數產生器；框架不會替外部語言設定 RNG。完整 Python 檔案範例見 [file_identity.py](../examples/file_identity.py)。

stdout 和 stderr 各保存為 log，不拿來當預測結果。非零退出碼、逾時、缺 response、非法 JSON、錯誤 task ID 或非法網格都記為該次失敗，評測繼續下一次；失敗仍留在分母內。逾時會終止直接啟動的程序，解法自行管理另開的子程序。這是本機可信程式的介面，不是隔離沙箱。

## 報告與重現

輸出目錄必須尚不存在，以免覆蓋或混合實驗。完成後會有：

- `report.html`：自含 SVG 圖表、方法比較、task × solver 成功率矩陣、tag 分組；不需網路或 CDN。
- `results.json`、`results.csv`：逐次保留方法、題目、seed、repeat、params、正確與否、test 分數、耗時、錯誤及 artifact 位置。
- `summary.csv`：各方法、各題／方法、各 tag／方法的次數、成功率、錯誤數及平均／中位耗時。
- `config.json`、`runs.jsonl`、`artifacts/`：設定快照、逐次追加紀錄、每次 request／response／stdout／stderr／run metadata。中途停止時可查已寫出的紀錄；完整報告於跑完後產生。

圖表的成功率是「答對整題的執行次數 ÷ 全部執行次數」。例如同一題跑四次只對一次就是 25%，不是 100%。多 test 題必須全部答對才算該次成功；timeout 和錯誤計入未成功次數。平均／中位耗時包含失敗程序以及程序與檔案處理成本，不是純演算法運算時間。

同一題可同時出現在多個 tag，tag 統計是重疊視角，不能相加當成整份資料集。CSV 中疑似試算表公式的文字會加單引號防止誤執行；原始文字完整保留在 JSON。需要重新處理資料時以 JSON 為準。

重現時保存程式 commit、編譯器／runtime 版本、設定檔與生成題 manifest。報告也保留題目內容 checksum；固定 seed 只在解法遵循 seed 且執行環境一致時有助重現。所有成績請標明公開 training、evaluation 或自訂／合成資料，不宣稱官方私有測試分數。
