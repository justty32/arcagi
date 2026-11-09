# 整夜鑄蠟模彙總（wax-night-1109）

寫於 2026-11-10 06:00:28（Asia/Taipei）。呼叫時間 2026-11-09T23:16:38 ～ 2026-11-10T06:00:28。

- 來源：reports/wax-night-1109/overnight/sol-prims_py/calls.jsonl
- 指令：`/home/lorkhan/repo/arcagi/src/arcagi/llm/wax/__main__.py summary-overnight reports/wax-night-1109/overnight`
- 模型：google/gemma-4-e4b（關 thinking）與 google/gemma-4-e4b+think（開 thinking）走 LM Studio，22:48 前與 2 個 aos agent **共用**（見「共用呼叫」欄），之後獨用；使用者約 23:00 關掉 LM Studio，gemma 兩組**中途關閉**、只有部分數據。chatgpt-* 走 litellm proxy（不用本機顯卡）。
- 擬合：`arcbatch --mode seed-sub`，預算 200k 節點，空樹 32 原語＋活樹 3 個 live 積木（reports/wax-night-1109/hammer-lib.json）；不改變任何格的步（no-op）已剔除。
- 狀態計數：ok 1307、no_code 810、error 424、badgrid 111、steps 28

## 各組合

| 模型 · 提示法 | 呼叫 | 有回覆 | 軌跡對齊 | 驗過 train | 每步可擬合（驗過的蠟模） | 全步可擬合（驗過的蠟模） | 全步可擬合且驗過／呼叫 | 每步可擬合（所有對齊軌跡） | 全步可擬合（所有對齊軌跡） | 有全步可擬合蠟模的題 | tok／呼叫 | tok／秒 | 牆鐘秒／呼叫 | 共用呼叫 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| chatgpt-gpt-6-sol-low · prims_py | 2680 | 2680 | 1307 | 851 | 1242/3021 = 41.1% | 215/851 = 25.3% | 215/2680 = 8.0% | 1966/4941 = 39.8% | 250/1307 = 19.1% | 28/296 | 899 | 49.9 | 18 | 0 |

## 題目層級

- 嘗試過的題：296
- 至少一個驗過蠟模的題：175
- 至少一個全步可擬合且驗過蠟模的題（28）：1e0a9b12, 25ff71a9, 2dee498d, 3c9b0459, 46442a0e, 496994bd, 4c4377d9, 6150a2bd, 62c24649, 67a3c6ac, 67e8384a, 68b16354, 6d0aefbc, 6fa7a44f, 74dd1130, 7fe24cdd, 8be77c9e, 8d5021e8, 9dfd6313, a416b8f3, beb8660c, c9e6f938, caa06a1f, d10ecb37, e9afcf9a, eb281b96, ed36ccf7, f25ffba3
