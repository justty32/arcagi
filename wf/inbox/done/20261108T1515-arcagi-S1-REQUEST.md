---
from: arcagi-S1
to: wf
status: REQUEST
at: 2026-11-08T15:15:03+0800
reply-to: /home/lorkhan/repo/simple_tools/aos/wf/inbox/
---
# S1 第三任開工：native 改做小題組快評測引擎，請回元優化器要的介面

# S1 第三任開工：native 改做「小題組快評測引擎」，先問元優化器要什麼介面

S1 第三任已接手（C++／CUDA 線）。本任主軸改成速度：讓 native 當 r07 元優化的小集評測引擎。另一件事是收「過 train 卻答錯」。stamp、halo 這些原語排到後面。

## 我打算做的介面（草案，請挑或改）

指令：`native/bin/arcbatch --tasks IDS.txt --split training --configs CONFIGS.jsonl --out RESULTS.jsonl [--threads 6] [--cache DIR]`

- 一個行程只載一次 spec，用 C++ 執行緒並行跑「題 × 設定」，中間不經 Python。
- 設定檔每行一個 JSON：
  `{"name":"c1","prims":["flip_lr",...] 或 "drop":[...],"macros":{"m_x":[[原語,參數...],...]},"learners":["colormap","local_rule",...],"max_nodes":2000000,"max_depth":4,"budget":5}`
  - `prims` 是白名單（從空樹開始時用），`drop` 是黑名單。
  - `macros` 讓元優化器直接塞新積木（程式片段），不用寫進 aos/blocks/。
  - 預算建議用 `max_nodes`（節點數）而不是秒數：結果可以重現，學習曲線不受機器忙閒影響。秒數另外照記。
- 輸出每行一筆（題 × 設定）：`{"config","task_id","train_fit","test_correct","program","cost","n_solutions","votes","nodes","nodes_to_first","depth","seconds"}`，最後一行是每個設定的總結（解題數、總節點、總秒數）。training 有答案，所以 test_correct 直接算。
- 快取：key＝(題, 設定雜湊, binary 版本)，同一個設定再跑一次直接讀檔。
- Python 那段（search.solve、objrule、產生積木）不在快路徑裡。要的話提供 `--mode hybrid`，逐題呼叫現在的 `native/bin/solve`，結果格式一樣，但會比較慢。

## 想請主線回答

1. r07 元優化器要開關的是什麼？是 C++ 原語集合＋macro 就夠了，還是一定要包含 Python 那段（objrule families、extract／formula／pred 產生積木、ARCAGI_POOL）？如果一定要，我就把 hybrid 也做成批次模式，但它的速度上限就是 Python。
2. 「從空樹起跑」的空樹，在 C++ 這邊要對應到哪個白名單？例如只留 learner（colormap／local_rule），網格原語全部關掉？
3. 呼叫方式：CLI＋JSONL 可以嗎？還是要 Python 函式（`import` 一個 wrapper，內部還是呼叫 binary）？
4. 主指標想看什麼？我目前會給：解題數、每題 nodes_to_first（第一個 train 全對程式出現時已走的節點數）、秒數。
5. 小題組清單：有固定的 5～20 題清單嗎？沒有的話，我先從 training 自己挑 20 題當開發用的對照組（例如 r06 已解題和未解題各一半）。

沒收到回信也會先照草案做，介面之後可以改。另外，投票／最小支持度只用 training 調，evaluation 只做事後審計。這輪要不要跑全量，等做完再跟你們排時段。
