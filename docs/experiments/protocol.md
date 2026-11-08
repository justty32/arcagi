# 接上任何語言的解法

[實驗教學](README.md)｜[設定檔](configuration.md)｜[排錯](troubleshooting.md)

每次執行建立獨立目錄，把 `{input}`、`{output}` 換成 request／response 的絕對路徑；`{trace}` 換成可選的嘗試軌跡檔路徑；也支援 `{task_id}` 與 `{seed}`。`command` 是 argv 陣列，直接啟動程序，不經 shell。可改成 `['node', 'solver.js', '{input}', '{output}']` 或 `['./solver', '{input}', '{output}']` 這類呼叫；JSON 設定檔內需使用雙引號。

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
  "params": {"budget": 100},
  "trace_path": "/abs/path/to/run/trace.json"
}
```

解法讀取 `task`，依 test 原順序寫出 response：

```json
{"example": [[[4]]]}
```

response 必須恰好包含此次 task ID，且每個 test 恰有一個合法網格。想留下嘗試過程，另把 [arcagi-trace/1](../traces.md) JSON 寫到 `trace_path`（即 `{trace}`）；不寫就沒有軌跡，寫壞只記 `trace_error`，不影響該次成績。解法自行解讀 `params`，也自行將 `seed` 套用到使用的亂數產生器；框架不會替外部語言設定 RNG。完整 Python 檔案範例見 [file_identity.py](../../examples/file_identity.py)。

stdout 和 stderr 各保存為 log，不拿來當預測結果。非零退出碼、逾時、缺 response、非法 JSON、錯誤 task ID 或非法網格都記為該次失敗，評測繼續下一次；失敗仍留在分母內。逾時會終止直接啟動的程序，解法自行管理另開的子程序。這是本機可信程式的介面，不是隔離沙箱。


## 可直接跑的非 Python 範例

- [sh_identity.sh](../../examples/sh_identity.sh)：POSIX sh＋sed，argv `["sh", "sh_identity.sh", "{input}", "{output}", "{trace}"]`；設定範例 [experiment-cross-language.json](../../examples/experiment-cross-language.json) 同時跑 Python 與 sh 兩種實作。
- [c_identity/solver.c](../../examples/c_identity/solver.c)：C99、無外部函式庫；`cc -std=c99 -O2 -o solver solver.c` 後用 `["./solver", "{input}", "{output}", "{trace}"]`。

兩者都只把 test input 原樣送回並寫一份示範軌跡，用來證明協議跨語言可行；它們用字串掃描取值，正式程式請用 JSON 函式庫。不想寫 experiment 設定，也可用 `arcagi eval --external "..."` 直接跑整份 split，見 [求解器介面](../solvers.md#外部程式直接跑整份評測)。

## Node.js 與 C++ 命令例子

以下替換設定檔內單一 solver 的 `command`；程式與 runtime 需自行準備。解法的命令列參數需與 argv 一致，並遵循上面的 request／response JSON 格式。

```json
["node", "solver.js", "--input", "{input}", "--output", "{output}"]
```

```json
["./build/solver", "--input", "{input}", "--output", "{output}"]
```

例如設定檔放 `examples/`、程式放 repo 根目錄，將該 solver 的 `cwd` 設為 `".."`；這樣 `solver.js` 或 `./build/solver` 都相對 repo 根目錄。C++ 先用自己專案的編譯流程產生 binary，再跑 experiment；框架不安裝編譯器或 JSON library。不要把 `cd ... && ...` 放成一個 command 字串，改用 `cwd` 和 argv 陣列。
