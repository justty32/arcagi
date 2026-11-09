# 鑄蠟模提示法比較（wax-night-1109）

← [progress](progress.md)｜完整表（含逐題）[compare-tables.md](compare-tables.md)｜任務信 [00-REQUEST](../../notes/rounds/gpu-night-1109/00-REQUEST.md) 第 1 條

**選定組合：`chatgpt-gpt-6-sol-low` × `prims_py`**，已用它啟動整夜長跑（systemd `arcagi-n1-overnight`，到 06:00，06:10 前寫 [overnight-summary.md](overnight-summary.md)）。

## 資料狀態

| 模型 | 狀態 | 筆數 |
|---|---|---|
| sol-low、luna-low（litellm） | **完整**：4 法 × 16 題 × 3 樣本，22:46～23:16 | 各 192 |
| terra-low（litellm） | **部分**：23:02 起跑，每次呼叫 50～100 秒，寫表時（23:2x）每法只有 8～9 筆；單元 `arcagi-n1-cmp-terra` 仍在跑、會續寫 `compare/calls-terra.jsonl`，結論不採用 | 33 |
| gemma-4-e4b（LM Studio，關 thinking） | **中途關閉**：22:48 前與 2 個 aos agent **共用**，使用者約 23:00 關掉 LM Studio | 128 |
| gemma-4-e4b+think | **中途關閉**，只有 3 筆 | 3 |

16 題 = `runner.COMPARE_TASKS`（含 r09 卡住的 b27ca6d3／74dd1130／2204b7a8 與活樹沒解的 L16／P48 題）。擬合 = `arcbatch --mode seed-sub`，預算 200k 節點，空樹 32 原語＋活樹 3 個 live 積木，結果回 Python 直譯器複驗。

## 主表

「驗過」= 模型程式在全部 train pair 上產生正確輸出。「每步可擬合（驗過）」= 驗過的蠟模裡，空樹在預算內擬合得到的步數比例。「全步可擬合且驗過／呼叫」= 每次呼叫拿到一個每步都可擬合、而且驗過的蠟模的機率（**選組合的主指標**）。

| 模型 · 提示法 | 呼叫 | 驗過 | 每步可擬合（驗過） | 全步可擬合且驗過／呼叫 | 每步可擬合（所有對齊軌跡） | 有全步蠟模的題 |
|---|---|---|---|---|---|---|
| **sol-low · prims_py** | 48 | 23 | **38/74 = 51.4%** | **10/48 = 20.8%** | 51/111 = 45.9% | 4/16 |
| sol-low · base | 48 | 34 | 22/53 = 41.5% | 10/48 = 20.8% | 24/62 = 38.7% | 4/16 |
| sol-low · prims_shot | 48 | 22 | 45/96 = 46.9% | 6/48 = 12.5% | 69/140 = 49.3% | 3/16 |
| sol-low · prims | 48 | 25 | 30/75 = 40.0% | 5/48 = 10.4% | 32/83 = 38.6% | 3/16 |
| luna-low · base | 48 | 24 | 6/32 = 18.8% | 4/48 = 8.3% | 14/59 = 23.7% | 2/16 |
| luna-low · prims_shot | 48 | 2 | 8/8 = 100% | 2/48 = 4.2% | 82/119 = 68.9% | 2/16 |
| luna-low · prims | 48 | 6 | 1/7 = 14.3% | 1/48 = 2.1% | 8/20 = 40.0% | 1/16 |
| luna-low · prims_py | 48 | 6 | 1/17 = 5.9% | 0/48 = 0% | 63/110 = 57.3% | 0/16 |
| terra-low · base（部分） | 9 | 8 | 3/15 = 20.0% | 1/9 = 11.1% | 3/16 = 18.8% | 1/9 |
| terra-low · prims（部分） | 8 | 3 | 4/9 = 44.4% | 0/8 = 0% | 7/21 = 33.3% | 0/8 |
| terra-low · prims_py（部分） | 8 | 2 | 3/5 = 60.0% | 1/8 = 12.5% | 7/20 = 35.0% | 1/8 |
| terra-low · prims_shot（部分） | 8 | 3 | 1/3 = 33.3% | 1/8 = 12.5% | 12/24 = 50.0% | 1/8 |
| gemma-e4b · 4 法（中途關閉／共用） | 32×4 | 0 | — | 0% | 多半回占位程式 `step("tag1", g)` | 0/16 |
| gemma-e4b+think（中途關閉） | 3 | 0 | — | 0% | — | 0 |

**為什麼選 sol · prims_py**：主指標與 sol · base 並列 20.8%（10/48）；扣掉一步就能整題擬合的 74dd1130（不算新原語來源）後仍並列 7/45。次指標「每步可擬合（驗過）」prims_py 51.4% 明顯高於 base 41.5%，代表它驗過的蠟模步更小、更貼空樹語言——這正是鑄模管線要的東西。sol · prims_py 的全步蠟模分布在 74dd1130×3、46442a0e×3、8d5021e8×2、7fe24cdd×2。

## 結構性發現

1. **換色步擬合不到**：空樹 lam 本體上限 4 節點，連「把 8 換成 2」都擬合不了，所以任何含換色的題至少一步必然擬合不到；每一種提示法都卡在這裡，不是提示能修的。
2. **附原語清單讓步變小，但弱模型因此解不對**：luna 加原語後「每步可擬合（所有對齊軌跡）」從 23.7% 漲到 57～69%，驗過卻從 24 掉到 2～6——模型把力氣花在湊小步，整體解法錯了。sol 較能兼顧（prims_py 驗過 23、步擬合 51%）。
3. **示範（prims_shot）沒幫上**：sol 的步擬合率最高（所有對齊 49.3%）但全步率掉到 12.5%，示範讓步切得更碎、多出一兩個擬合不到的步。
4. **74dd1130 整題一步可擬合**（`--direct` 標出），這類題的蠟模不算新原語來源，比較時要扣除。
5. 全部 16 題只有 4 題拿到任何全步可擬合蠟模；r09 卡住的 b27ca6d3／2204b7a8 仍零。

## 下一步建議（一句）

**先改語言，不改提示**：讓空樹能表達換色（放寬 lam 本體上限或加一個 `recolor(a→b)` 原語）——現在提示法之間的差距（20.8% vs 10%）比換色這道硬牆小，換色不解決，再好的提示也有一大類題拿不到全步可擬合蠟模。

## 指令與 commit

- 程式：`src/arcagi/llm/wax/`（c835198 起；本棒加 `overnight --offset`）。
- 比較：`WAX_SCRATCH=$S .venv/bin/python -m arcagi.llm.wax compare --models chatgpt-gpt-6-sol-low,chatgpt-gpt-6-luna-low --samples 3 --workers 3 --threads 2 --out reports/wax-night-1109/compare/calls-gpt.jsonl --wax reports/wax-night-1109/compare/wax --name cmp-gpt`（terra 同法，`--models chatgpt-gpt-terra-low`）。
- 彙總：`WAX_SCRATCH=$S .venv/bin/python -m arcagi.llm.wax summary reports/wax-night-1109/compare/calls-*.jsonl --direct --out reports/wax-night-1109/compare-tables.md`（terra 跑完後重跑此行即可更新）。
- 整夜：`systemd-run --user --scope -q --unit=arcagi-n1-overnight nohup sh reports/wax-night-1109/run-overnight.sh sol-prims_py chatgpt-gpt-6-sol-low prims_py 2`（內層 `arcagi-n1-on-sol-prims_py`）。
- `$S` = `/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n1`。
