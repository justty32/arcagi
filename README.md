# arcagi

第一次使用可先開啟 [圖解教學與小測驗](docs/tutorial.html)：用格子圖看懂題目、解法、評分與實驗比較，下載後可離線閱讀。

用自己的方法挑戰 ARC-AGI-1：官方公開題庫、可重現的衍生題目、求解器介面、精確比對評測與離線題目瀏覽器。不需要 GPU、模型或機器學習套件；`training` 只是官方題庫的目錄名稱。

第一次操作請看 [逐步教學：跑完第一個實驗](docs/experiments/quickstart.md)，或依目的瀏覽 [使用教學總覽](docs/README.md)。

## 開始使用

需要 Git、[uv](https://docs.astral.sh/uv/) 與 Python 3.12 以上。從專案根目錄執行：

```sh
uv sync --locked
uv run python scripts/setup_data.py
uv run python scripts/setup_data.py --check
uv run pytest -q
uv run arcagi validate --split training --require-test-outputs
uv run arcagi validate --split evaluation --require-test-outputs
uv run arcagi visualize --split training --output artifacts/training.html
```

用瀏覽器開啟 `artifacts/training.html` 即可看題。HTML 完全離線，只渲染目前選取的題目，可瀏覽整份 400 題；測試答案預設折疊，仍包含在檔案內。

```sh
# 用原樣輸出輸入的 identity 求解器，確認整條評測流程可運作
uv run arcagi eval --split evaluation --solver identity --output artifacts/identity.json

# 從 RE-ARC 規則產生新範例，與官方題庫分開存放
uv run arcagi generate --task 007bbfb7 --seed 0 --count 5 --output data/generated/demo
uv run arcagi visualize data/generated/demo/tasks --output artifacts/generated.html
```

跨語言、多方法與重複試驗使用同一套檔案介面：

```sh
uv run arcagi experiment examples/experiment.json --output artifacts/experiment-demo
```

開啟 `artifacts/experiment-demo/report.html` 查看成功率圖表、單題與題型比較；同目錄保留逐次 JSON、CSV 與彙總 CSV。[設定與介面說明](docs/experiments.md)。

評測採 **top-1**：每個 test 輸入只交一個預測，網格尺寸與每格顏色全部相同才算答對；一題所有 test 都答對才算解出該題。這是本地測試指標，不代表官方競賽提交分數。

- [題庫來源與產生器](docs/data.md)：公開資料、固定版本、授權與再現方式。
- [接上自己的求解器](docs/solvers.md)：Python plugin 或外部程式的 JSON 預測。
- [測試與實驗流程](docs/testing.md)：驗證、跑分、結果判讀及防止資料混用。
- [開發環境](wf/workflows/dev-env.md)、[工作流入口](wf/WORKFLOWS.md)、[CI](.github/workflows/tests.yml)。
