# wax-night-1109 交棒（23:03，context 到 30% 換手）

← 任務信 [00-REQUEST](../../notes/rounds/gpu-night-1109/00-REQUEST.md)

## 做到哪

- **程式完成並有測試**：`src/arcagi/llm/wax/`（client／prompts／sandbox／fit／runner／`__main__`），`tests/llm/wax/test_wax.py`（8 綠）。純 stdlib。
  - 模型回 `solve(grid)` 程式（每步呼叫 `step(tag, g)`），本機沙箱子程序（`python -I`、CPU 10s、1GB、15s 逾時）跑出軌跡；no-op 與「繞回舊狀態」的步會收掉；各 pair tag 序列要一致（否則 `unaligned`）。
  - 每步 `(S_i, S_{i+1})` 丟 `arcbatch --mode seed-sub`，預算 200k、空樹 32 原語＋活樹 3 個 live 積木（`hammer-lib.json`），結果回 Python 直譯器複驗；段內容 hash 快取。
  - 4 種提示法：`base`（r09 鑄模規矩，對照）、`prims`（＋32 原語清單＋便宜步範例）、`prims_py`（＋原語當 `P.*` Python 函式、每步一個 `P` 運算式、禁迴圈）、`prims_shot`（`prims_py`＋一個示範）。
  - 模型維度：`google/gemma-4-e4b`（LM Studio，關 thinking）、`google/gemma-4-e4b+think`、litellm 的 `chatgpt-gpt-6-sol-low`、`chatgpt-gpt-6-luna-low`、`chatgpt-gpt-terra-low`。
- **比較跑了一部分**：16 題（`runner.COMPARE_TASKS`，含 r09 卡住的 b27ca6d3／74dd1130／2204b7a8 與活樹沒解的 L16／P48 題）。
- 規則變化已照辦：LM Studio 被使用者關掉 → gemma 兩組停（**中途關閉**，22:48 前「共用」）；所有批次包 `systemd-run --user --scope --unit=arcagi-n1-<名> -p MemoryMax=16G nice -n 19`；`~/arcagi-STOP` 存在時迴圈停；整夜改到 06:10 前結束（soft 06:00、hard 06:07，彙總 06:09 前）。

## 數字（23:02 中途，未完）

| 組合 | 呼叫 | 驗過 | 每步可擬合（驗過） | 全步可擬合且驗過／呼叫 | 每步可擬合（所有對齊） |
|---|---|---|---|---|---|
| gemma-e4b（關 thinking）各法 | 32×4 | 0 | — | 0% | 低（多半回占位程式 `step("tag1", g)`） |
| gemma-e4b+think | 3 | 0 | — | 0% | 中途關閉 |
| sol-low base | 21 | 14 | 47.6% | 23.8% | 40.0% |
| sol-low prims_py | 21 | 11 | 50.0% | 23.8% | 40.4% |
| sol-low prims | 21 | 11 | 44.7% | 9.5% | 43.6% |
| sol-low prims_shot | 21 | 10 | 42.5% | 14.3% | 47.6% |
| luna-low base | 21 | 13 | 15.8% | 9.5% | 20.0% |
| luna-low prims_py／prims_shot | 20／21 | 3／0 | — | 0% | 62%／70%（步小但解不對） |

初步觀察：附原語清單讓步變小（所有對齊軌跡的每步可擬合率上升，luna 最明顯），但 luna 因此常解不對；sol 的 `prims_py` 在「每步可擬合（驗過）」與「全步可擬合且驗過／呼叫」並列最好。空樹連「把 8 換成 2」都擬合不了（lam 本體上限 4 節點），所以有換色的題至少一步必然擬合不到。注意 74dd1130 整題一步就可擬合（交 summary `--direct` 會標出），這類題的蠟模不算新原語來源。

## 在跑

| systemd 單元 | 做什麼 | 輸出 | 日誌 |
|---|---|---|---|
| `arcagi-n1-cmp-gpt.scope` | sol-low＋luna-low × 4 法 × 16 題 × 3 樣本（可續跑，會跳過已有的） | `reports/wax-night-1109/compare/calls-gpt.jsonl` | `$S/cmp-gpt.log` |
| `arcagi-n1-cmp-terra.scope` | terra-low × 4 法 × 16 題 × 3 樣本 | `reports/wax-night-1109/compare/calls-terra.jsonl` | `$S/cmp-terra.log` |

`$S` = `/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n1`（擬合快取 `fitcache-*.jsonl`、模型原文 `raw-*.jsonl`、arcbatch 工作夾）。驗過的蠟模（foundry 格式）寫在 `reports/wax-night-1109/compare/wax/`。

## 下一步（接手者）

1. 等兩個單元結束（`systemctl --user is-active arcagi-n1-cmp-gpt.scope arcagi-n1-cmp-terra.scope`）。
2. 彙總：`WAX_SCRATCH=$S .venv/bin/python -m arcagi.llm.wax summary reports/wax-night-1109/compare/calls-*.jsonl --direct --out reports/wax-night-1109/compare-tables.md`，據此寫 `compare.md`（表＋結論＋可重跑指令＋commit 雜湊；標明 gemma 22:48 前共用、23:00 中途關閉）。挑最佳＝「全步可擬合且驗過／呼叫」最高（次看每步可擬合（驗過））。
3. 啟動整夜（例：最佳是 sol-low prims_py；另可並跑一條 luna／terra 便宜組）：
   `systemd-run --user --scope -q --unit=arcagi-n1-wrap-<名> nohup sh reports/wax-night-1109/run-overnight.sh <名> <模型> <提示法> 2 > $S/on-<名>.log 2>&1 &`
   內層單元 `arcagi-n1-on-<名>`；296 題（training、train 格數 ≤1200、排除 H8／H24），一輪一題一樣本循環到 06:00；結束（或被 TERM）時寫 `reports/wax-night-1109/overnight-summary.md`（合併所有 `overnight/*/calls.jsonl`），外層再補寫一次。
4. 寫 `notes/rounds/gpu-night-1109/wax-白話.md`；commit（只 add 自己路徑）＋ `git pull --no-rebase` ＋ push。
5. code-map 尚未登記 `llm/wax`（code-map 在 wf/ hub，可寫範圍外，留給主 session）。

## 關鍵路徑

- 程式：`src/arcagi/llm/wax/`；測試：`tests/llm/wax/test_wax.py`
- 腳本：`reports/wax-night-1109/run-overnight.sh`；活樹積木：`reports/wax-night-1109/hammer-lib.json`
- 原始數據：`reports/wax-night-1109/compare/calls-*.jsonl`
