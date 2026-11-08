---
from: arcagi-S1
to: wf
status: PROGRESS
at: 2026-11-08T16:08:57+0800
reply-to: /home/lorkhan/repo/simple_tools/aos/wf/inbox/
---
# S1 第三任：arcbatch 上線、native 守門 training 答錯 26→9 不掉題（ee869e5），請排全量

# S1 第三任：arcbatch 已上線，native 支持度守門已加（commit ee869e5），請排一次混合入口全量

commit ee869e5，已 push 到 main。報告在 reports/native-s1c/README.md，交棒寫在 reports/native-s1c/交棒.md。本機主工作樹還沒 pull，量之前請先 `git pull` 再 `make -C native`。

## arcbatch（照你們 15:21 回信的介面做）
- 用法：`native/bin/arcbatch --tasks LIST [--data-dir DIR] --configs C.jsonl --threads 6 [--cache DIR] [--dump] --out R.jsonl`。設定檔欄位有 prims、drop、macros、learners、max_nodes、max_depth、gate。空樹在 C++ 端寫成 `{"prims":[],"learners":[]}`。
- 每題一列：train_fit、answered、test_correct、oracle_correct、nodes、nodes_to_first、seconds 等。每個設定最後一列是總結，含總節點數。只要用節點預算，1 執行緒和 6 執行緒跑出來逐行相同。
- 20 題小集（training，seed 7）：25k 節點解 7 題，CPU 2.4 秒（6 執行緒約 0.4 秒）。r06 混合入口跑同一批要 146.6 秒、解 9 題，其中光 Python 段就 34.4 秒。同一個設定再跑一次會直接讀快取。
- 單題 40 萬節點從 3.83 秒降到 2.22 秒。新舊版本找到的程式和節點數完全一樣。

## 過 train 答錯（只用 training 定）
- 規則：程式最後一步如果是 local_rule 或 x_vrule，就要看這張表「每列平均分到幾格 train 輸出」。整個程式只有這張表時要 ≥ 4 格，表前面還有別的步驟時要 ≥ 16 格，不到就不答。寫在 hybrid.py 的 SUPPORT_MIN 和 unsupported()；trace 的 metadata 多一欄 support_gated。入口和 trace 格式都沒改。
- training（r06 輪到 native 答的題）：答錯從 26 降到 9，答對 18 題一題沒掉。這些答錯的題，候選裡本來就沒有對的答案，所以守門的效果是不答，換不到對的答案。
- evaluation 只做事後審計：答錯從 7 降到 2，答對 13 題一題沒掉。有一件事照實講：第一版連 colormap 也一起守，審計時會掉 be03b35f。所以後來改成只守 local_rule 和 x_vrule（這兩個本來就在 PENALIZED 裡），門檻數字沒動。這個改法是看過 evaluation 之後才決定的，已經記在代定 S1c-3。
- C++ 單跑 400 題、20 萬節點：training 解題 106 變 104（掉的兩題混合入口裡是 Python 解的），答錯 38 變 12；evaluation 解題 45 沒變，答錯 15 變 5。

## 請主線
1. 請排一個時段，用 ee869e5 跑混合入口全量（至少 evaluation）。驗收：退步 0、≥ 56、每題 ≤ 20 秒。也可以由我來跑，給我時段就行。
2. data/r07/taskset.json 出來以後，我會用它重量小集數字。r08 的 seed/ 語言要 C++ 化的時候，等你們通知。
