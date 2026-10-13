# 測試與實驗流程

先確認環境與官方題庫通過檢查，再加入自己的方法。無須 GPU、模型權重、API key 或訓練服務。

## 一次完整驗證

```sh
uv sync --locked
uv run python scripts/setup_data.py --check
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv run arcagi validate --split training --require-test-outputs
uv run arcagi validate --split evaluation --require-test-outputs
uv run arcagi eval --split evaluation --solver identity --output artifacts/identity.json
```

pytest 檢查資料格式、求解器介面、正確／錯誤答案計分、CLI、生成器與 HTML 輸出。CI 也會安裝固定相依版本、跑 lint 和測試，並確認兩份官方公開 split 各有 400 題。

## 開發一個解法

先保存修改前的 evaluation 報告，再針對少量 training 題目探索規則、撰寫有正反例的測試，最後用完全相同的 split 與參數重跑。報告至少記錄程式 commit、solver 名稱、資料來源、題目數與解出題數；生成題另保存 manifest。快速迭代可以加 `--limit 10`，但題目會依檔名排序取前 N 題，這不是隨機樣本，也不是完整評測成績。

不要拿 evaluation 答案反覆調參後仍把結果當作未看過題目的泛化表現。合成題、training、公開 evaluation 各自產生報告；若需要自己的保留集，先決定規則族或任務的分割，再開始改解法。

## 多方法、題型與重複試驗

以 [experiment](experiments.md) 設定明確的 task 清單、自訂 tags、方法參數、seeds 和 repeats，所有方法跑同一矩陣；可用 `--task` 或 `--tag` 做單題／題型測試。HTML 和 CSV 的成功率以逐次執行為分母，失敗和逾時不移除；不要把重複試驗中任一次成功當成整題 100%。每次實驗使用新的輸出目錄，保留 config、request／response、log 和結果。

## 讀懂分數與退出碼

本環境使用 exact-match top-1：尺寸和每格顏色完全一致才算 test 答對；一題有多個 test 時必須全部答對才算解出。報告的 `tasks_correct / tasks_total` 是整題準確率，`tests_correct / tests_total` 是測試範例準確率，`errors` 是求解器執行或預測格式失敗的題數。JSON 中的 accuracy 是 0–1 比例。

官方原版任務說明允許每個 test 多次嘗試，本環境只計一次預測，因此請把結果標為「公開 evaluation、top-1、解出 X/400」，不要當成官方競賽提交成績。題庫內沒有官方私有測試集。

命令退出 `0` 代表成功執行，包含答案全錯但格式正確的情況；`1` 表示評測報告有求解器或預測失敗，`2` 表示輸入／設定錯誤，`130` 表示中斷。不要以退出碼 `0` 當作解題準確率合格，應讀取報告中的數字。

新增驗證規則時，同時測試應通過與應拒絕的例子。例如合法 0–9 矩形應通過，空網格、ragged rows、布林值或超過 9 的顏色應被拒絕。HTML 的結構與 escaping 有自動測試；實際視覺體驗仍可用 `visualize` 輸出的檔案人工檢查。
