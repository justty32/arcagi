# S2 交接（aos-llm 蒸餾）

← [第一任報告](llm-s2/README.md)｜[第二任報告](llm-s2b/README.md)

## 現況（2026-11-08 15:00，第二任）

- 第一任：eval20 test exact 7/20；候選 34 個、live 2 個。
- 第二任已做：
  - `dsl.md` 加了 `n_holes` 和 S1 的 `x_ray`／`x_connect`／`x_compress`／`x_crop_color`／`x_period`／`x_vrule`（`prompt_hash` 因此改變）。
  - s40：r05 沒解的 training 40 題（seed 20261108，清單 [s40-ids.txt](llm-s2b/s40-ids.txt)）。15 題過 train，15 題 test 全對。
  - gen1：10 題靠大表硬湊過的解法（表最大 1656 列）叫 LLM 改寫成短規則（表 ≤8 列）。9/10 過，test 全對。
  - 工具 `python -m arcagi.llm distill stage|reuse`：把解法切成片段積木，在兩份 blocks root（`ARCAGI_BLOCKS`）上跑 search A/B，再用合成集算每個用法的通過率。
  - 缺原語分類：[llm-s2b/missing.csv](llm-s2b/missing.csv)。
- 正在跑：A/B（`<scratchpad>/ab.sh`），等主線全量跑完才開始。腳本內容：先 `distill stage OUT`，然後在 `OUT/base` 和 `OUT/llm` 各跑一次 `arcagi eval --split training --solver arcagi.solvers.search:solve --timeout 45 --workers 6`（nice、MemoryMax=8G），最後 `ARCAGI_BLOCKS=OUT/llm python -m arcagi.llm distill reuse OUT OUT/base.json OUT/llm.json --record`。

## 怎麼接著跑

1. 寫提示：`nice -n 19 uv run python -m arcagi.llm prompts --split training --ids …`
2. 開 opus subagent，同時最多 3 個，4 題一批。提示照抄：「Follow the instructions in …/aos/llm/prompts/solver.md exactly, once per task… Step 5 is mandatory: unless train already passes, run `check` at least 4 times…: TASKS=… SPLIT=… RUN=…」。不寫「至少 4 次」的話，agent 常常 check 一次就放棄。
3. `record`，token 和秒數按批平均。之後跑 `rescore`、`summary --csv reports/llm-s2b/RUN.csv`。
4. 改寫大表（gen 型）：同一份提示，再加「表 ≤8 列、colormap ≤4 對」的限制。

## 坑

- `macro` 只要含 `colormap`／`object_colormap`／`local_rule`，registry 就不會載入。所以 distill 會跳過含這些學習終端的片段，`x_vrule` 也一起跳過。
- `x_*` 原語在 Python search 裡不會被提出（`PYTHON_SEARCH=False`）。包成 macro，Python search 才拿得到，例如 `x_period fill 0`、`x_connect hv`。
- 合成集會換顏色。寫死顏色的積木（`x_period fill 0`）在合成集上大多不過。
- 工作樹是共用的：先 `git fetch`，只 add 自己的路徑。
