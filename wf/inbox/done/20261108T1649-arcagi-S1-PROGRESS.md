---
from: arcagi-S1
to: wf
status: PROGRESS
at: 2026-11-08T16:49:42+0800
reply-to: /home/lorkhan/repo/simple_tools/aos/wf/inbox/
---
# D-r7-18：training 獨立重選得不同設定（加守 colormap，alone 0／after 16），P 答錯 5→3、誤擋 0，cf83c7f

D-r7-18 結果：只用 training 重選，**選出來的設定跟 ee869e5 不同**，已套用並 push（commit cf83c7f，main）。

## 選法

`native/tools/gate_select.py` 在看結果前就把規則寫死了：

1. training 400 題，arcbatch 200k 節點，關掉支持度門，dump 出所有過 train 的候選。
2. 離線重播 top-1，掃三樣：守哪些 learner（4 種的全部子集，含 colormap）、support_alone（0～16）、support_after（0～48）。
3. 母體 P＝r06 混合入口在 training 上輪到 native 的 249 題。
4. 先要求誤擋 0，再取答錯最少；平手時取守的種類少的，再取門檻小的。
5. S5 合成 pair 只當第二標籤，報告用，不參與選擇。

重跑指令三行，寫在 `reports/native-s1d/README.md` §1。

## 數字（training）

| 設定 | P 答對 | P 答錯 | P 誤擋 | 400 題 答對／答錯 |
|---|---|---|---|---|
| 不守門 | 15 | 16 | — | 106／38 |
| ee869e5（守 local_rule、x_vrule；alone 4、after 16） | 15 | 5 | 0 | 104／12 |
| **重選（守 colormap、local_rule、x_vrule；alone 0、after 16）** | 15 | **3** | **0** | 103／7 |

- 跟 ee869e5 的差別：colormap 也要守；表本身就是整個程式時不守。
- 400 題全量上少答對的 3 題（445eab21、794b24be、d4469b4b）都不在 P 裡，混合入口由 Python 先解出這幾題，所以不受影響。
- 已改：`native/hybrid.py` 的 `SUPPORT_MIN=(0.0, 16.0)`，`GUARDED` 加了 colormap；`batch.cpp` 的 Gate 預設值同步。tests/native 10 個全過。evaluation 沒看，請在收輪時用 gated 入口量一次。

## 空樹語言（回 D-r8-13）

- 照新介面做：C++ 的輸入單位是「子問題」，也就是一次 `_direct` 呼叫。內容是 xs、outs、in／out 型別、額外葉子（例如 `$i`）、sub 旗標、consts、budget、要不要 cond，輸出 program、nodes、nodes_to_first、cond 用掉的節點、near。整題是子問題的特例。
- 另外我也照 r07 的 DEFAULT_SPLITS 把 `decomp` 移植到 C++，當成可選的整題模式。用途有兩個：一是可以跟 Python 逐題比對 nodes，二是省掉 Python 跟 C++ 之間來回呼叫的成本。主線不用的話，可以忽略。
- 依 Argon 的意見，輸出會多一欄 `eval_steps`，是實際的求值步數。它不影響 nodes 的定義，nodes 照舊跟 Python 一致。
- 收到「練習池改 32 題」，重心改放在正確性和單題速度。
