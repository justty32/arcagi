# 實驗排錯

[實驗教學](README.md)｜[輸入輸出契約](protocol.md)｜[結果欄位](results.md)

先看終端退出碼和報告的 `errors`。命令退出 0 只表示執行成功，並不代表解對；答案格式合法但全錯可以是 0 分、0 errors。完整實驗有求解器失敗會退出 1，設定或資料錯誤退出 2，中斷退出 130。

## 尚未開始執行

**輸出目錄已存在**：使用新的 `--output`，例如 `artifacts/run-002`。既有結果保留作為比較，不要清空後假裝是同一次實驗。

**找不到 task、cwd 或程式**：task `path` 和 solver `cwd` 相對於設定 JSON 的所在目錄；命令內的程式路徑再相對於 cwd。從 repo 根目錄執行 CLI 不會改變這個規則。使用 [設定範例](configuration.md) 的路徑時，設定檔要放在 `examples/`。

**設定 schema 錯誤**：確認 `version` 是整數 1、tasks 與 solvers 非空、名稱唯一、`command` 是字串陣列、`repeats` 是正整數、timeout 是正的有限數值。未知欄位、重複 JSON key、不存在的 tag 或 task ID 都會被拒絕。

## 某個解法失敗

由 `results.json` 的失敗 run 找 `artifact_dir`，開其中的 `stderr.log`、`stdout.log` 和 `run.json`。若流程中途停止，先看輸出根目錄的 `runs.jsonl`；完整 HTML／CSV 只在跑完後產生。

**沒有 response／JSON 無效**：程式要把答案寫到 `{output}` 指定的檔案，不是只印到 stdout。確認不是把 debug 訊息混入 response；JSON 只能有此次 task ID，值是按 test 順序排列的網格清單。網格必須矩形、尺寸 1–30、顏色為整數 0–9，布林值不合法。

**timeout**：檢查 `timeout_seconds` 和演算法搜尋預算。先以 `--task` 跑一題定位，再決定是否放寬時限；不要從報告剔除逾時紀錄。框架會終止直接程序，解法額外建立的子程序由解法管理。

**非零退出碼**：先看 stderr，檢查 runtime／binary 是否可用、argv 是否符合解法定義。命令不經 shell，`cd`、`&&` 或重導向不能直接當 shell 語法使用；改用 cwd 和獨立參數。

## 分數或圖表看不懂

同題四次只有一次答對是 25%，不是 100%；多 test 題需每個 test 都正確。不同 tag 可以包含同一題，不能把 tag 的次數加總成總題數。若要檢查單次預測，從 raw JSON 或該次 response 看內容；瀏覽官方標準答案時避免讓解法讀到它。
