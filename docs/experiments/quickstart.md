# 跑完第一個實驗

[實驗教學](README.md)｜[遇到問題](troubleshooting.md)

以下命令都在 repo 根目錄執行。需要 Git、uv；Python 最低版本為 3.12。不需要 GPU、模型或機器學習套件。

## 1. 準備一次環境

```sh
uv sync --locked
uv run python scripts/setup_data.py
uv run python scripts/setup_data.py --check
uv run pytest -q
```

第一次需網路取得 Python 相依與固定版本題庫。setup script 會只取得 RE-ARC 必要原始碼，避免大型預生成 ZIP；不要改用 recursive submodule checkout。`--check` 應回報官方 training、evaluation 各 400 題；pytest 應全部通過，某些未安裝 Node 的環境會略過可選 Node 測試。

## 2. 不改程式，先跑完整範例

```sh
uv run arcagi experiment examples/experiment.json --output artifacts/first-experiment
```

終端應顯示 `runs_total: 16`、`errors: 0`：兩題 × 兩方法 × 兩 seeds × 兩 repeats。範例方法只是 identity 與全零輸出，**0 分很正常**；這一步確認測試流程，沒有要求它解出題目。

用瀏覽器直接開啟 `artifacts/first-experiment/report.html`。頁面包含成功率圖表、方法耗時、單題矩陣及題型統計；Excel 或其他分析工具可以開同目錄的 `results.csv` 和 `summary.csv`。要保留完整原始資料則使用 `results.json`。詳細欄位見 [結果說明](results.md)。

再次跑同一命令會因輸出目錄已存在而拒絕覆蓋。把 `--output` 換成新的名稱，例如 `artifacts/first-experiment-v2`；不必刪除舊實驗。

## 3. 只測一題或一種題型

```sh
uv run arcagi experiment examples/experiment.json --task 007bbfb7 --output artifacts/one-task
uv run arcagi experiment examples/experiment.json --tag fill --output artifacts/fill-tasks
```

這兩個命令各應得到 `runs_total: 8`、`errors: 0`。`fill` 是範例設定自訂的 tag，並非官方分類。多個 tag 取聯集，與 task 篩選合用則取交集；細節見 [設定說明](configuration.md)。

## 4. 開始比較自己的方法

保留原範例，另存一份設定在 `examples/`，例如 `examples/my-experiment.json`；修改 solver 的 `command`、`params` 與 `name`，再執行：

```sh
uv run arcagi experiment examples/my-experiment.json --output artifacts/my-method-v1
```

同一解法的不同參數使用不同 `name`；每種方法會跑同一批題目、seeds 和 repeats。照 [檔案介面](protocol.md) 接程式，照 [設定說明](configuration.md) 加方法與題目。每次改動保存新的結果目錄，才能比較改前和改後。
