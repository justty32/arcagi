# dsl-search-r05：原始碼空間改寫搜尋＋子樹積木（參數槽）＋每物件規則 8 向／兩步讓 evaluation 解 ≥40（挑戰 42）、同大小 ≥16

- 指令（`systemd-run --user --scope -q -p MemoryMax=16G nice -n 19` 下跑，開跑前 `pgrep -af "arcagi eval"` 無人在跑、`git status aos/blocks aos/pool` 乾淨）：
  `uv run arcagi eval --split evaluation --solver arcagi.solvers.search:solve --name dsl-search-r05 --timeout 45 --workers 6 --output artifacts/r05/dsl-evaluation.json --traces artifacts/r05/dsl-evaluation-traces.jsonl`（training 同指令換 `--split training`）；commit `ae8f213`。
  比較 `uv run arcagi compare r04=artifacts/r04/dsl-evaluation.json r05=artifacts/r05/dsl-evaluation.json --format markdown`；記帳 `uv run python -m arcagi.blocks.pool --report artifacts/r05/dsl-evaluation.json --epoch 5 --split evaluation`。
  收緊（commit 見 git log「slot macros are rewrite-only」）後只重跑受影響題：r05 軌跡裡任一過 train 程式含 `m_sub_*` 的題（evaluation 10、training 24），`--tasks-dir` 子集、輸出 `artifacts/r05/msub-{evaluation,training}.json`。
- 結果（全量）：**evaluation 38/400**、**training 96/400**，errors 0；同大小 evaluation **14/270**（r04 13）、training 46/262（r04 44）。每題最長 29.8 秒；evaluation 逐題耗時合計 1974 秒（r04 641，×3.1——改寫每題最多 8 秒，在 BFS 無解的 ~360 題都跑）。
- 收緊後（全量＋受影響子集拼接）：evaluation 38、training **95**；過 train 答錯 evaluation 17→**14**、training 32→**26**（r04 13／24）。
- 基準：dsl-search-r04 evaluation 37、training 92；**退步 0**（兩個 split）。
- 結論：**否**——evaluation 38 未達保底 40，同大小 14 未達 16；training 95 未達 100。過 train 答錯 training 26 ≤27 達到（收緊後）。

## 觀察

- evaluation 新解 1：`2a5f8217`＝`recolor_from` 用 C 線新選擇器 `same_shape_other_color`（同盤面同形的圖例物件取色）。
- training 新解：`1f876c06`（`extend_from` 斜向 `dir8_to`）、`5521c0d9`（`move_by` 距離＝物件高）、`feca6190`（**改寫搜尋**解出：近失敗＋`param_neighbors`／`insert_step`）、`239be575`（改寫＋槽積木 `m_sub_133be74a`；收緊後失去）。
- **改寫搜尋**：evaluation 0 解、training 1～2 解；evaluation 每題平均試 ~3000 候選、多數用完預算。B 線子集也是 0/50。鄰域改寫在現行原語上幾乎找不到過全部 train 的程式——近失敗的「差一點」多半差的是原語表達不了的東西，不是參數。
- **子樹積木（帶槽）**：落地 3 個（`m_sub_b181a7a9` 13 題共用、`m_sub_00fed9e8` 7、`m_sub_133be74a` 4）；放進 BFS 時讓搜尋多走一層，新增過 train 答錯 training 6 題／evaluation 3 題（都以 `local_rule` 收尾）→ 收緊為「只給改寫用」。
- janet 往返：844 物件（全部積木 program/_rule、training 解出程式）100%，janet `parse-all` 844/844。
- C 線新原語新增過 train 答錯：`move_by`（training 1caeab9d、evaluation 64a7c07e）、`move_from` 斜向（training a48eeaf7）；保留（training 各有 1 解）。

## aos 帳（epoch 5）

- 收入 38000、守恆成立；真退休 59 個（extract 26、formula 33：產生器積木＋連 3 epoch 0 收入＋covered）。`generator_budget` extract 42%／formula 33%／pred 26%（與 epoch 4 同：新解沒用到產生器積木）。

## 支線對照（核過）

- native-s1（S1，C++ 補 Python）：`artifacts/native-s1/eval-v2.json` evaluation **42/400**；對 r05 compare：新解 358ba94e、5ffb2104、d56f2372、f5aa3634，退步 0（S1 跑在 r05 施工中的工作樹上，r06 用最新 HEAD 重跑一次）。

## 下一步

- 改寫搜尋預設仍開（training +1）但耗時 ×3：r06 先用合成集（S5）與 training 判斷是否只對近失敗 IoU 高的題開。
- 同大小池：S3 開（清單 `notes/rounds/r05/S3-training-same-size-unsolved.txt`）；C++ 寬樹（S1）證明「物件原語不限第一步」有效，主線吸收。
