支線 S1（C++ 搜尋引擎）交接：給下一任 arcagi-S1 隊長。

- 讀：[04 總結](native-s1/04-總結.md)（成績、代定、下一步）、[02 設計](native-s1/02-設計.md)、[03 量測](native-s1/03-量測.md)。
- 程式：`native/src/`（C++20，`make -C native`；bin/ 與 spec.json 由 Makefile 產生）、`native/hybrid.py`（外部協議入口，主線先跑、C++ 補、Python 重驗）、`native/export_spec.py`、`native/tools/parity_smoke.py`；測試 `tests/native/`（parity 43,762 筆＋搜尋）。
- 現況：evaluation 42/400（r04 37），退步 0，每題 ≤19 秒。已寄 PROGRESS 給主線；ROSTER 已追加 `arcagi-S1`，但那份檔沒 commit（wf/ 是主線的）。
- 規矩：只寫 native/、reports/native-*/、tests/native/；全量評測前先跑 `pgrep -af "arcagi eval"`，用 workers ≤6、MemoryMax=8G、nice 19；codex 照圖紙寫碼，圖紙範例在 aos scratchpad，已不在。
- 下一步：見 04 總結「下一步」第 1 項：要新原語，得先寫信請主線開註冊介面。
