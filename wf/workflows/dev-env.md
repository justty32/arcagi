# dev-env — 開發環境與指令

[WORKFLOWS](../WORKFLOWS.md)｜[INDEX](../INDEX.md)｜[README](../../README.md)

**何時用**：fresh clone、換機器、安裝問題或查指令。驗證流程見 [testing](testing.md)，資料來源見 [題庫文件](../../docs/data.md)。專案不需要 GPU、機器學習環境或 API key。

## Done when

從乾淨 checkout 完成下列步驟，題庫來源檢查與 `uv run pytest -q` 都回傳 0。

## Fresh clone

需要 Git 與 [uv](https://docs.astral.sh/uv/getting-started/installation/)。Python 最低版本以 `pyproject.toml` 為準，目前為 3.12；套件版本固定在 `uv.lock`。在 repo 根目錄執行：

```sh
uv sync --locked
uv run python scripts/setup_data.py
uv run python scripts/setup_data.py --check
uv run pytest -q
```

首次安裝依賴與題庫需網路。之後的測試、評分、產生題目、瀏覽均可離線；目前沒有必填環境變數。若從其他位置安裝套件，生成器可用 `ARCAGI_ROOT` 指向此 repo 的完整 checkout；正常使用不必設定。執行 plugin 時 Python 模組須可匯入，放專案根目錄的 `my_solver.py` 可直接以 `my_solver:solve` 載入。

## 常用操作

```sh
uv run arcagi --help
uv run arcagi validate --split evaluation --require-test-outputs
uv run arcagi solve data/ARC-AGI/data/training/007bbfb7.json --solver identity
uv run arcagi eval --split evaluation --solver identity --output artifacts/identity.json
uv run arcagi generate --task 007bbfb7 --seed 0 --output data/generated/demo
uv run arcagi visualize --split training --output artifacts/training.html
```

`uv run python -m arcagi` 等同 `uv run arcagi`。自訂資料目錄在 `eval`／`score` 用 `--tasks-dir`，在 `validate`／`visualize` 直接給路徑。`generate` 的輸出目錄必須尚不存在；題目在其 `tasks/` 子目錄。

求解器契約與外部預測格式見 [solvers](../../docs/solvers.md)。新增／升級相依需依 [user](common/user.md) 的授權邊界處理並更新 lock；不額外加入 ML 或繪圖套件。

## 交接

環境就緒後進 [feature-dev](feature-dev/README.md)；安裝問題反覆發生時記到 [gotchas](common/gotchas.md)。
