# testing — 跑測試與驗證

[WORKFLOWS](../WORKFLOWS.md)｜[INDEX](../INDEX.md)｜[實驗流程](../../docs/testing.md)

**何時用**：改完程式、跑測試、重構前記基準。環境未建立先看 [dev-env](dev-env.md)。

## Done when

相關測試與 lint 通過；commit 前完整 pytest 通過。求解器改動另附同份 evaluation 的改前／改後解出題數；合成題分數另列。需要使用者處理的驗證才登記 [WAIT_USER](../WAIT_USER.md)。

## 必跑指令

```sh
# 迭代中：快速定位第一個失敗
uv run pytest -x -q

# commit 前：完整驗證
uv run ruff check .
uv run ruff format --check .
uv run pytest

# 題庫或載入器變動時
uv run python scripts/setup_data.py --check
uv run arcagi validate --split training --require-test-outputs
uv run arcagi validate --split evaluation --require-test-outputs

# 求解器改動前後：替換為相同的 plugin 與不同輸出檔名
uv run arcagi eval --split evaluation --solver identity --output artifacts/identity.json
```

以上由 agent 執行。命令成功不等於答對題目；評測採 top-1 整題 exact match，讀 `tasks_correct`、`tasks_total`、`errors`，不要只看退出碼。未提供 test 答案不能評分，求解器異常不可自總數移除。細節見 [solvers](../../docs/solvers.md)。

CI 在 [tests.yml](../../.github/workflows/tests.yml) 執行固定依賴安裝、lint、pytest 與官方兩份 split 的題數驗證。本機不需要 GPU、模型、外部服務帳號或訓練流程。

## 檢查必須能變紅

新增或修改檢查時，要有應通過和應拒絕的例子。合法網格應通過；空網格、長短列、非法顏色應被拒絕。計分測試至少包含正確答案、錯誤尺寸、多 test 題只答對一部分與求解器失敗，確保錯誤不會被略過。

靜態與結構測試不能證明畫面體驗正確。HTML 可先確認沒有外部資源、字串已 escaping、答案折疊，再開啟產出的 HTML 檢視。只有實際看過才能宣稱目視驗證；必要且無法自行完成的目視驗證，另記 WAIT_USER。

生成器測試應使用臨時目錄和固定 seed，避免修改官方題庫或污染 evaluation。新增大型生成 sweep 先估執行時間，保存 manifest 和失敗資訊。

## 交接

驗證完成後回 [feature-dev](feature-dev/README.md)，同步 code map、文件並依授權 commit／push。
