# 設定方法、參數與題型

[實驗教學](README.md)｜[先跑一遍](quickstart.md)

完整可執行設定見 [examples/experiment.json](../../examples/experiment.json)。最小設定如下；`path` 與 `cwd` 都相對於設定檔所在目錄，將下列內容放在 `examples/` 才能直接使用這些路徑：

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


`repeat` 在結果中從 0 起算；seeds 不可重複，想重跑同一 seed 請增加 `repeats`。params 由解法自行理解，框架只傳遞，不會自動改演算法。
