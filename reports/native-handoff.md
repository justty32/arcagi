支線 S1（C++ 搜尋引擎＋新原語）交接：給下一任 arcagi-S1 隊長。

- 讀：[05 第二輪](native-s1/05-第二輪.md)（新原語語意、數字、代定、下一步），以及第一輪 [04 總結](native-s1/04-總結.md)、[02 設計](native-s1/02-設計.md)。
- 程式：C++ 在 `native/src/`（新原語在 `prims_ext.cpp`）；Python 在 `src/arcagi/dsl/ext/prims.py`，經 `EXT_PRIMS` 註冊。`PYTHON_SEARCH = False`：Python 只負責執行與重驗，不出候選。入口是 `native/hybrid.py`。開發量法用 `native/tools/cpp_only.py`（可帶 `--spec`；用 `ARCSEARCH_BIN` 換 binary）。測試：`tests/native/`（含 ext parity）、`tests/dsl/ext/`。
- 現況：commit `45668f9`，新原語 6 個（x_ray、x_connect、x_compress、x_crop_color、x_period、x_vrule）。parity 127,390 筆全一致；training 子集 C++ 單跑 1→9/53。evaluation 全量交主線 15:20 用 45668f9 跑，**結果還沒回信**，驗收是退步 0、≥45、每題 ≤20 秒。
- 規矩（r06 起）：入口契約、trace 格式由主線決定，不能改；`aos/blocks/` 不能寫。全量評測由主線跑，主線量的是已 commit 的 native/。**工作樹跟主線共用**：主線量測期間，native/ 不要留沒 commit 的改動，開發請用 git worktree 或 scratchpad 編的 binary。
- 下一步：先看主線的全量回信（若有退步，先查是不是 x_vrule 或 x_ray 的便宜程式在投票時贏了）。之後照 S4 優先序加 stamp（往標記處蓋印範本）、halo（描邊／畫框）、以物件為中心的對稱修補。
