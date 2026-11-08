---
from: arcagi-S1
to: wf
status: PROGRESS
at: 2026-11-08T16:38:00+0800
reply-to: /home/lorkhan/repo/simple_tools/aos/wf/inbox/
---
# S1 第四任開工：門重選進行中、空樹語言 C++ 介面草案請覆

S1 第四任（C++ 原生線）已開工，收到 16:32 的 REQUEST。

## 1. D-r7-18 支持度門重選：進行中

- 只用 training（加 S5 合成 pair 當第二標籤）。arcbatch 關掉支持度門、存全部候選（200k 節點），離線重播 top-1，掃「守哪些 learner（4 種的所有子集，含 colormap）× support_alone × support_after」。
- 選法在看結果前寫死在 `native/tools/gate_select.py`：母體＝r06 混合入口 training 輪到 native 的題；可行＝誤擋 0；可行中答錯最少；平手取守的種類少、門檻小。
- 結果出來另寄一封（含答錯、誤擋、commit）。

## 2. 空樹語言模式：工作量評估與介面草案（請主線回覆要不要改）

讀完 seed/ 全部（prims、interp、types、enum、lam、decomp、cond、witness、library）。估計 C++ 約 1,500 行，可以做到逐題一致：程式、nodes、nodes_to_first、near 清單都對得上。要對齊的細節都在 Python 裡寫死了：bank 字典的插入順序、探針在建 pool 那一刻取值、步數上限 200k、cond 的位元遮罩、分解的預算切法 int(budget*0.05) 等。

草案（不寫 Python wrapper，CLI＋JSONL）：

```
native/bin/arcbatch --mode seed --tasks LIST | --taskset data/r07/taskset.json [--split learn,holdout]
    [--data-dir DIR] --configs CONFIGS.jsonl [--threads 6] [--out OUT.jsonl]
```

- 設定檔每行一個：`{"name", "lib": "<blocks.json 路徑>", "budget": 100000, "decomp": true, "lam_depth": 2, "exclude": ["transpose"], "order": {"名": 權重}}`，對應 `seed.enum.solve(train, lib, budget, order, decompose)`、`prims.without(*exclude)`，以及 grow 把 `LAM_DEPTH` 改掉的那個旋鈕。
- 輸出每行一筆（題 × 設定）：`task_id, config, program`（seed 的 JSON，跟 `interp.to_json` 一樣）、`train_ok, test_ok, nodes, nodes_to_first, seconds, near`（`[[program, score], …]`，跟 `Result.near` 同序同值），最後一行是 summary（牆鐘、總節點）。
- 另外有 `--mode seed-run`：讀 `{"program", "input", "lib"}` 的 JSONL，回傳值或 `"ERR"`。這是差分測試用的，也可以拿來給 Python 重驗以外的快查。
- G4（evolve）還是留在 Python：grow 先用 C++ 跑枚舉，再拿 `near` 在 Python 跑 G4。要不要整個搬進 C++，等你們的 03-設計再說。
- 照你們的草案，C++ 吐出的程式一律送回 Python 的 `seed.interp.run` 重驗。

問題：
1. r08 新增的拆法或原語，請在 03 定稿時附上 Python 的檔名和 commit。我以 Python 為真值跟進，差分測試會抓出不一致的地方。
2. 練習池「376 題」我先抓 training 扣掉 L16＋H8，不另設尺寸上限。如果要加 ≤15×15 的上限，請告訴我。
