# 嘗試軌跡（arcagi-trace/1）

[求解器介面](solvers.md)｜[跨語言檔案介面](experiments/protocol.md)｜[比較與逐題對錯](solvers.md#比較方法與逐題對錯)

求解器可以**選擇性**回報每題「試了什麼」：試過的假設或程式、各自在訓練範例上的驗證結果、最後選了哪個、耗時與自由文字推理。量具逐題保存下來，供之後蒸餾成可重用規則。軌跡**完全不影響計分**；不回報的求解器照常運作，軌跡格式錯誤只記成 `trace_error`，預測照樣評分。

## 怎麼回報

- **Python plugin**：回傳 `SolverResult(predictions, trace)`（`arcagi.solvers.trace`）取代單純的網格清單。最方便的寫法是用 `TraceRecorder`，範本見 [template.py](../src/arcagi/solvers/template.py)。
- **外部程式**：把軌跡 JSON 寫到 `{trace}` 指向的檔案；同一路徑也放在 request 的 `trace_path` 欄位。不寫這個檔就等於沒有軌跡。執行失敗（非零退出、response 錯誤）時寫出的軌跡也會保留，方便分析失敗原因。

## 格式

每題一個 JSON 物件，所有欄位都可省略；省略 `schema_version` 會補成 `arcagi-trace/1`、省略 `attempts` 會補成空清單。

```json
{
  "schema_version": "arcagi-trace/1",
  "solver": "my-solver",
  "attempts": [
    {
      "id": "h1",
      "kind": "hypothesis",
      "description": "每個物件往下掉到底",
      "program": "(gravity down)",
      "train_results": [true, true, false],
      "train_correct": 2,
      "train_total": 3,
      "selected": false,
      "elapsed_seconds": 0.12,
      "reasoning": "第三組有障礙物",
      "error": null,
      "data": {"llm_tokens": 812}
    }
  ],
  "selected": "h1",
  "reasoning": "整題的自由文字推理",
  "elapsed_seconds": 1.5,
  "metadata": {"model": "..."}
}
```

attempt 欄位：`id` 是題內唯一字串，頂層 `selected` 引用它（null 表示沒有可用假設）；`kind` 是自訂分類（`hypothesis`、`program`、`llm`…）；`description` 給人看、`program` 放可重跑的程式或 DSL；`train_results` 依 train 順序記錄是否重現每組輸出，`train_correct`／`train_total` 是通過數與總數（`TraceRecorder` 自動算）；`selected` 標記最後提交的那個；`elapsed_seconds` 是耗時；`reasoning`、`error` 是推理文字與失敗訊息；`data` 放任意附加資料。

頂層欄位：`solver` 名稱、`reasoning` 整題推理、`elapsed_seconds` 總耗時、`metadata` 任意附加資料。

已知欄位的型別會被檢查（布林不可冒充整數、數值不可為 NaN 或負數）；未知欄位原樣保留。單題軌跡上限 10 MB。

## 存在哪裡

- `arcagi eval`：完整報告每題多了 `elapsed_seconds`、`trace`、`trace_error`，頂層 `traces` 是有軌跡的題數。加 `--traces PATH.jsonl` 另寫一份逐題 JSONL，每行是 `arcagi-trace-record/1`：`solver`、`task_id`、`correct`、`tests_correct`（逐 test 布林）、`error`、`elapsed_seconds`、`trace`、`trace_error`。這份檔把軌跡和對錯接在一起，最適合拿去蒸餾。
- `arcagi experiment`：`results.json` 與 `runs.jsonl` 的每次 run 有 `trace`、`trace_error`；外部程式寫的原始檔留在該次 `artifacts/.../trace.json`。`results.csv` 只放 `trace_error`。

報告裡的 `correct` 是用標準答案評的；軌跡本身只來自求解器，不含答案。
