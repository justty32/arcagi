# N9：提高 max_nodes 能多解幾題？→ BLOCKED（前提不成立）

結論：主線 training 的「預算型放棄」撞到的是**時間上限**，不是 max_nodes 2e6。
主線路徑裡 max_nodes 其實是 2e7，而且從來沒有被撞到。所以調 max_nodes 不會多解任何題；
真正綁住的是 `native/hybrid.py` 裡寫死的 19 秒期限，沒有命令列參數或環境變數能改。
依任務規則**沒有改原始碼，也沒有跑批**（沒有任何 n9 systemd 單元）。

## 1. 主線實際呼叫鏈與參數（全部唯讀查證）

| 層 | 檔案:行 | 傳的參數 |
|---|---|---|
| gated | `src/arcagi/solvers/gated.py` `_run_hybrid`（約 345–355 行） | 只呼叫 `native/bin/solve req out trace`，`timeout=60`；沒有搜尋參數 |
| solve | `native/bin/solve` | `exec .venv/bin/python native/hybrid.py "$@"` |
| hybrid | `native/hybrid.py:9` `DEADLINE = T0 + 19.0` | 整題 19 秒期限，寫死 |
| hybrid | `native/hybrid.py:195` `budget = DEADLINE - time.perf_counter() - 4.0` | 呼叫 arcsearch 時給 `--budget`（扣掉 seeds 階段後約 13–15 秒），**不傳 `--max-nodes`／`--max-depth`** |
| arcsearch | `native/src/search.hpp:6-8` | 預設 `budget=19.0`、`max_depth=5`、**`max_nodes=20000000`（2e7）** |
| arcsearch CLI | `native/src/main.cpp:81-83` | 支援 `--budget`、`--max-depth`、`--max-nodes`，但 hybrid 不傳 |

`batch.cpp:124-126` 的 `budget 60 / max_depth 4 / max_nodes 2e6` 只是 **arcbatch**（`--batch`）的預設值，
不在 gated 主線上。01-簡報 §3 把它當成主線參數，這點有誤。

## 2. trace 證據（`artifacts/gated-r07/training-traces.jsonl`，out_of_budget=True 共 195 筆）

- nodes：最小 46,817，中位數 1,527,149，**最大 4,644,388**。有 58 筆超過 2e6，**0 筆達到 2e7**。
  如果真有 2e6 的節點上限，就不可能出現超過 2e6 的值。
- elapsed：最小 1.8 s，中位數 13.2 s，最大 14.9 s。這正好是 19 秒減 4 秒，再減 seeds 階段的時間。
- 吞吐中位數約 12 萬節點/秒（停在 d3 的 148 筆）。

## 3. 若要量「給更多搜尋」，需要改哪裡（未改）

- **時間（真正的瓶頸）**：`native/hybrid.py:9` 的 `19.0`，連帶 `:195` 扣的 `4.0`。
  另外 `gated.py` 的 `timeout=60` 是外層上限：期限超過約 55 秒就會被它截斷。
- **節點**：要在 `native/hybrid.py:207-219` 的 arcsearch argv 加 `--max-nodes N`。
  現在只有時間在綁，這一項沒有意義。
- 合規的替代做法（不碰主線）：建議加一個環境變數，例如 `ARCAGI_HYBRID_DEADLINE`（預設 19.0），
  在 hybrid.py 讀取。這需要 lead 決定是否改原始碼。
- 粗估（下界，用 d3 部分節點推分支因子，很粗）：停在 d3 的 148 題中，
  要把 d4 走完所需秒數的中位數約 90 s（p10 約 10 s，p90 約 260 s）。
  期限 60 s 可走完約 58 題，180 s 約 112 題。這只代表「d4 走得完」，不代表會解出來。
  假解率要實際跑過才知道。

## 4. arcbatch-hot

`arcbatch-hot`（N8）的改動只在 seed 語言（`native/hot/seed_value.cpp`、`seed_enum.cpp`，
走 `--batch --mode seed`），不涉及主線 `search.cpp`／arcsearch 的列舉。
它不能當 arcsearch 的同介面加速替身，所以沒有 1e7+hot 這一組。

## 5. evaluation

沒有跑，因為沒有可測的設定。

## 下一步（給 lead）

若同意改 hybrid.py 加上期限的環境變數（只加開關，預設不變），就能在 188 題母體上跑
deadline ∈ {19, 40, 55}，量新增 test 對、假解與衝突。55 是受 gated `timeout=60` 限制的上限；
想跑更長，gated 的 timeout 也要一起開放成可調。

---

# N9b：主線 hybrid 期限改成可調，在 188 題預算型放棄母體上掃期限（跑中）

## 開關（commit 0eaf09d）

- `native/hybrid.py:11`：`DEADLINE = T0 + float(os.environ.get("ARCAGI_HYBRID_DEADLINE") or 19.0)`。`:195` 扣的 `4.0` 不動。`import os` 移到這一行前面，T0 仍然在其他 import 之前量。
- `src/arcagi/solvers/gated.py`：新增 `_hybrid_timeout()`，讀 `ARCAGI_GATED_TIMEOUT`，預設 60。`_run_hybrid` 的 argv 不變。
- 未設時行為不變的證據：
  - 單元測試 `tests/solvers/test_hybrid_deadline_env.py` 驗證：未設時 DEADLINE−T0 = 19.0、gated timeout = 60、`_run_hybrid` argv 與改前相同；設值時兩者都會生效。`tests/solvers` 共 153 passed。
  - 小樣本 3 題（007bbfb7、0a938d79、1e0a9b12），未設和明設 `=19` 各跑一次：selected 相同、correct 相同、abstained 相同，arcsearch 耗時都約 13.3 s（和 r07 trace 一致）。
- 實作：codex（gpt-6.1-sol）。

## 掃描設定

- 母體：`n9b-tasks.txt`，共 188 題，是 r07 training 裡 out_of_budget＝True 且 abstained 的題目。
- 腳本：`n9b_sweep.sh`。d19 不設環境變數，作為基準；d40、d55 用預設的 gated timeout 60；d120 另外設 `ARCAGI_GATED_TIMEOUT=130`。harness `--timeout` 設成期限加 25 s 到 30 s，workers 6。
- 判讀：`n9b_analyze.py`。進度和接手方式見 `n9b-progress.md`。

## 結果

（跑中，見 n9b-progress.md）

## N9b 結果（主 session 04:13 收，n9b_analyze.py 原樣）

| deadline | 作答 | test 對 | 假解 | 新增 test 對 vs d19 | 新增假解 vs d19 | 衝突 | 仍逾時 | 耗時和 s |
|---|---|---|---|---|---|---|---|---|
| 19 | 3 | 1 | 2 | — | — | — | 186 | 2927 |
| 40 | 2 | 1 | 1 | 0 | 0 | 0 | 185 | 6881 |
| 55 | 4 | 2 | 2 | 1（a3df8b1e d4） | 1（d8c310e9） | 0 | 182 | 9605 |
| 120 | 7 | 3 | 4 | 2（＋e3497940 d3） | 3（7f4411dc、ae3edfdc、d8c310e9） | 0 | 174 | 19472 |

註：d19 重跑在 188 題「r07 放棄」母體上作答 3 題，表示 r07 的放棄本身受計時抖動影響。

**判讀**：把期限從 19s 拉到 120s（6.6× 算力）只多 2 題 test 對、卻多 3 題假解，174/188 題仍逾時。這批題不是「差一點時間」，而是搜尋空間本身太大／原語不夠；加時間不划算。**建議**：期限維持 19 預設；開關留著供實驗。剩餘資源宜投在縮小空間（原語、剪枝、排序）而非加時。
