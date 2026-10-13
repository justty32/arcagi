# 題庫與產生器

官方 [ARC-AGI](https://github.com/fchollet/ARC-AGI) 以 submodule 存於 `data/ARC-AGI/`，固定 revision 由 Git 記錄，包含公開 `data/training/` 400 題和 `data/evaluation/` 400 題。兩份公開資料都附測試答案；官方未公開測試集不在這裡，也不能從公開資料下載取得。`training` 在此指題庫分組，專案沒有機器學習訓練環境。

每個任務 JSON 有 `train` 和 `test`；每個範例有 `input` 與可選的 test `output`。網格是矩形、寬高各 1–30，顏色為整數 0–9。載入器會拒絕不合法格式；沒有 test 答案的題目可以求解和瀏覽，但不能做有答案的評分。

## 安裝與驗證

```sh
uv run python scripts/setup_data.py
uv run python scripts/setup_data.py --check
uv run arcagi validate --split training --require-test-outputs
uv run arcagi validate --split evaluation --require-test-outputs
```

第一次安裝會初始化官方題庫與 RE-ARC submodule，需要網路。請使用上述 setup script；RE-ARC 以 partial clone 加 sparse checkout 只取得需要的原始碼，避免一般 recursive submodule checkout 同時下載大型 ZIP。後續題庫驗證、求解、評測、生成與瀏覽可離線執行。`--check` 檢查題數、固定來源版本、來源檔案校驗及官方題目的 schema；`arcagi validate` 也能單獨檢查自訂題目。官方 Apache-2.0 授權見 [LICENSE](../data/ARC-AGI/LICENSE)。更新來源應另行檢查題數、校驗和與基準分數，不要直接漂移到上游最新版本。

## 產生更多題目

[RE-ARC](https://github.com/michaelhodel/re-arc) 提供從 ARC training 題目重建的 400 個規則產生器及驗證器。必要原始碼以固定版本 submodule 保存在 `vendor/re-arc/`，MIT 授權見 [LICENSE](../vendor/re-arc/LICENSE)。本專案沒有下載大型預生成題庫，也不需要繪圖或 ML 相依套件。

```sh
uv run arcagi generate --list
uv run arcagi generate --task 007bbfb7 --seed 42 --count 10 --output data/generated/example
uv run arcagi validate data/generated/example/tasks --require-test-outputs
uv run arcagi eval --tasks-dir data/generated/example/tasks --solver identity --output artifacts/generated-score.json
uv run arcagi visualize data/generated/example/tasks --output artifacts/generated.html
```

`--task` 可重複指定；`--all` 選擇全部 400 個規則。`--count` 是每個規則產生幾題，預設每題 3 組 train、1 組 test；可用 `--train-examples` 與 `--test-examples` 調整。`--difficulty-lower`、`--difficulty-upper` 控制產生器的難度參數，並不是經人類或求解器校準的難度分數。`--timeout` 限制每題生成時間，預設 60 秒。

輸出目錄內的 `tasks/` 使用同樣的官方 JSON 格式，`manifest.json` 記錄來源、seed 與生成設定。重現實驗時保留 manifest 和 Python 版本，並使用相同程式版本與參數。輸出目錄必須尚不存在，以免覆蓋或混合實驗。manifest 的 `complete` 可辨認生成是否完整完成。

合成題只代表這些規則族的新範例，不是新的官方測試集；在合成題做出的進步不能直接宣稱為 ARC-AGI-1 的泛化進步。不要把合成題塞入官方 evaluation 目錄，評測報告也要分開保存。
