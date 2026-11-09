# 收線驗收

對證據、不對自我宣告；核 commit、清背景程序、更新看板。

1. 逐條核驗收：數字自己重跑或讀輸出檔核。
2. 核 commit 狀態（今晚應為本機 commit、未 push）。
3. 背景程序清乾淨（`systemctl --user list-units 'arcagi-*'`）。
4. 跨資料夾交接書移 `done/`。
5. 看板「現役線」移「已收線」，附證據（commit、數字）；更新 SESSION-LOG。
6. `PARTIAL` 的線：開新 agent 從 `progress.md` 接手，交接書只帶產物路徑、不帶對話。
7. 收完大改進線 → 開下一輪思考設計輪（見 `think_round`）。

完整版：`wf/workflows/dispatch/README.md`「流程」第 6 步。
