# N8c：arcbatch-hot-e 實作與驗證

HOT_E 建立於 HOT_A+HOT_B；僅在全部 `lam_nodes[k] < 0` 且 primitive 在白名單時批次評估。

改動檔案：
- `native/hot/scalar_prims.hpp`：共用 inline 語意與 `template<int P>` 批次 kernel。
- `native/hot/seed_enum.cpp`：switch 移至範例迴圈外；從 flat 的各參數連續區段讀取。
- `native/hot/seed_value.cpp`：HOT_E 的 apply_prim 共用上述語意，其餘分支保留原文。
- `native/Makefile`：只追加 hot-e 目標；enum/value 在 obj-e 以 A+B+E 重編，其餘沿用 A+B objects。
- `tests/native/test_arcbatch_hot.py`：加入 hot-e parity 參數與 scalar C++ 檢查。
- `tests/native/hot_e_check.cpp`：隨機／邊界值、原始 handles、步數、ERR 部分寫入及完整 Store 狀態比較。
- 本報告；`native/src/` 未動，Makefile 舊內容逐 byte 保留。

批次涵蓋 18 個 prim：ADD SUB MUL NEG MOD EQ LT MAX MIN AND OR NOT IF LEN NTH HEAD LAST COUNT。
各 case 本體與修改前 ADD..LAST、COUNT 已逐 byte 核對；HOT_E interpreter 與 kernel 共用同一份。
保留 chk_int、MUL __int128、Python MOD、NTH 檢查順序、py_eq/py_lt 及回傳原 handle 的語意。

排除 TAKE DROP REVERSE CONS APPEND CONCAT RANGE REPEAT SORT TRANSPOSE：可能呼叫 Store::make。
MAP FILTER ZIPWITH FOLD：高階呼叫可能執行 lambda、寫 Store 並消耗步數。
任何 lambda 參數及不在白名單內的操作均走原本 eval_prim 迴圈。
批次 kernel 不讀寫 steps；白名單原呼叫的 cx.steps 本來不變。
emit() 僅在成功時將 vals 傳入 offer()；失敗時只記 nodes，trace 也不讀 vals。
kernel 仍於同一 j 寫 ERR 後立即返回，保留未處理後綴；沒有新增 Store 寫入或 intern 順序變化。

驗證（2026-11-10 03:1x，沙箱 systemd user bus 不可用）：
- `timeout 55 nice -n 19 make -C native hot-e -j4`：成功。
- 未定義 HOT_E：base、A、A+B、A+B+C、A+B+D × enum/value 共 10 份，
  `g++ -std=c++20 -E -P -Inative/src` 對修改前快照全部逐 byte 相同（-P 去除行號標記）。
- `uv run --no-sync pytest -q tests/native/test_arcbatch_hot.py`：11 passed，8.90 秒；修改前 8 passed。
  外層 timeout 55／nice 19，關閉 pytest cache，暫存與 uv cache 均導向 scratchpad。
- scalar 單元檢查分別連結原 A+B 與 E evaluator，兩者 assertions 與輸出摘要一致。
- 變更的 Python 檔案：ruff check、ruff format --check 通過；git diff --check 通過。
- 1e6：training 排序前 100 題、seed、decomp=true、4 threads，兩個程序各 timeout 55／nice 19。
  `reports/cpu-hot-1110/cmp.py`：**0/100 mismatches**，僅排除 seconds，保留 eval_steps／near 順序／JSON 型別。

單跑 1e6 牆鐘（各一次，非正式 bench；loadavg 為啟動時 1／5／15 分鐘值）：
- arcbatch：10.370429 秒，loadavg 11.24／11.95／13.39。
- arcbatch-hot-e：8.758969 秒，loadavg 11.82／12.05／13.41。

原始輸出、預處理快照、建置／pytest log、wall.json、parity.json 均在使用者指定 scratchpad 的 n8c/。
未跑 1e7、正式 bench、CUDA；未 commit，未啟動任何 n8c systemd 單元。
