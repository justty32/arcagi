# seed-forbid-1110 進度

- [x] S1 `forbid` 實作：`native/src/seed_enum.cpp`（根樣式比對、每個 op 預先建好樣式索引、在 `Enumerator::emit` 求值前擋下）、`seed_main.cpp`（設定行 `forbid`、每題 set_forbid／計數、`forbidden` 欄只在有 forbid 時出現）、`seed_enum.hpp`。
- [x] `native/Makefile` 新增 `make forbid` → `native/bin/arcbatch-forbid`（全部原始碼編成一支，用法 `arcbatch-forbid --batch --mode seed ...`）。`bin/arcsearch`、`bin/arcbatch` 沒重編。
- [x] `tests/native/test_seed_forbid.py`：沒給 forbid 時輸出跟舊 `bin/arcbatch` 逐欄相同（decomp 開／關）、等價樣式不改程式且 nodes_to_first 剛好少掉被擋數、萬用字元語意。
- [x] 量測：training 前 100 題，預算 1e5／1e6／1e7 × {base, fb（規格 9 條）, fb2（規格＋10 條冪等）}；預算 1e6 再交錯重複 3 次量時間。見 `report.md`。
- [x] `seed-gpu-可行性.md`。

未做：lambda 體池（BodyPool）裡不套 forbid（只擋主列舉器的根）。

關鍵路徑：原始量測 jsonl 在 scratchpad `/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n5/`（res-*.jsonl、tim-*.jsonl、analyze.py），不 commit。
