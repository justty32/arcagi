# N8d：arcbatch-hot-f 實作與驗證

改動檔案：`native/hot/seed_value.cpp`、`native/Makefile`、
`tests/native/test_arcbatch_hot.py`、`tests/native/hot_f_check.cpp`、本報告。

HOT_F 建立在 A+B+E；只於 eval 的 kid 迴圈直接解 CONST／INPUT／VAR／LAM。
其餘 kind 遞迴原 eval；LAM 使用 A.kids 中的子節點 index 建立原 handle。
Makefile 僅追加 hot-f：enum/value 在 obj-f 以 A+B+E+F 編譯，其他沿用 HOT_AB_OBJECTS。
父節點仍保留原 CNode 拷貝；kid 參考在分派時讀取，遞迴返回後不再存取。

步數與早停：
- 原葉節點在 `native/hot/seed_value.cpp:724` 起直接返回，早於 :730 的扣步數。
- :738 起 inline 分支同樣不扣步數；內部節點仍在 :730 扣 1，早於 :732 的 kid 迴圈。
- 非葉節點在 :742 遞迴；:747 的共用 ERR 早停保留，包含 VAR 越界及 INPUT／VAR 為 ERR。
- `call()` 未改；:705 的 before_steps 與 :711 的差值快取完全保留。
- enum 的 eval 呼叫與 eval 頂層入口未改；未定義 HOT_F 的原遞迴行保留於 #else。

驗證（2026-11-10 03:4x；systemd user bus 沙箱不可用，均以 timeout 55／nice 19 限時）：
- `make -C native hot-f -j8` 成功。
- 未定義 HOT_F：base、A、A+B、A+B+C、A+B+D、A+B+E × enum/value 共 12 份，
  `g++ -std=c++20 -E -P -Inative/src` 結果與修改前快照逐 byte 相同。
- Makefile 舊內容前綴逐 byte 相同；seed_enum.cpp 完全相同。
- `uv run --no-sync pytest -q tests/native/test_arcbatch_hot.py`：14 passed，12.77 秒（原 11 passed）。
  pytest cache 關閉，uv cache／暫存／建置 log 均置指定 scratchpad。
- C++ 檢查連結 E／F：20 組本體 × 10 預算 × eval／call／重複 call，
  逐字比較原始 handle、剩餘 steps、Store 全欄位；另斷言耗盡／不足、ERR 前後配置與 LAM index。
  包含 CONST／INPUT／VAR 越界／LAM、巢狀 MAP、配置型 MAP、FILTER、ZIPWITH、FOLD 與 A 快取邊界。
- 1e6：training 排序前 100 題、seed、decomp=true、4 threads；arcbatch／E／F 均成功。
  `reports/cpu-hot-1110/cmp.py`：E、F 對 arcbatch 均 **0/100 mismatches**，保留 eval_steps／near 順序／JSON 型別。
- ruff check、ruff format --check、git diff --check 通過。
- native/src、run_one.py、n8d_bench.sh 與既有 hot／hot-e 二進位 SHA-256 均未變。

快照與 log：指定 scratchpad 的 `n8d/`（preprocessor.log、build.log、pytest.log、wall.json、*-parity.json）。
未 commit；未啟動 n8d systemd 單元；全套測試與正式 bench 由主 session 處理。
