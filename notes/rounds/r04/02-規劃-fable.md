第四輪規劃：fable 只讀 [01-簡報](01-簡報.md) 後的回覆，原樣存檔。

← [交棒總表](../README.md)｜下一步 [03-設計](03-設計.md)

# 第四輪規劃（fable）

## 範圍（一句）

主做 **D1 每物件各自規則**（同大小池），配 **D3 預算真的執行＋D7 拆 pool.py**，**D2 只做「抽取值當公式特徵」**，**D4 溫和加大**；D5、D6 延到第五輪。

## 求解器與積木方法

- **每物件規則＝「動作＋參數來源」**。沿用四型外殼，不加第五型：transform 的 body 允許參數欄寫成 `{"from": "<extract 積木名>"}`，執行時對**每個物件**各跑一次該 extract 積木取值。extract 積木新增「物件視角」選擇器：`this`、`nearest`、`nearest_same_color`、`touching`、`largest`、`wall_dir`；屬性加 `color`、`dir_to`、`dist_to`、`size_rank`。
- **擬合**：每個 train pair 做物件對齊（位置重疊／顏色），算出每物件的目標參數（新色、位移向量、延伸方向）；枚舉物件視角 extract 積木，保留對**所有 train 物件一致**者；多個一致時取帳上分數高者。
- **防背答案**：train 內目標參數至少 2 種不同值、涉及物件 ≥3；參數來源只能是 `gen_extract` 產出的積木，禁人手寫死；輸出仍走最短程式。
- **公式**：特徵集加入 top-20（帳分）抽取值；2 層只在 1 層失敗後才試，形式限 `a·x+b·y`、`(x+c)·y`、`max/min(x,y)`，係數 `a∈{1,2,3,-1}`、`b,c∈[-2,2]`，每次產生上限 3000 候選。
- **搜尋**：`MAX_DEPTH=3` 不動、`MAX_NODES` 2 萬→10 萬、`TIME_BUDGET` 5→20 秒；用 `predict_shapes` 剪枝：中間格無法到達預測尺寸者不展開。本輪不開 C++／CUDA。

## aos 接入

- 積木：`aos/blocks/objrule_*/`（transform 含 `from` 參數）、`aos/blocks/ext_obj_*/`（物件視角抽取）。
- 帳：extract 積木**被當參數來源**時與該程式同分紅（解決 extract 分紅 0）；`generator_budget` 由「只記」改為「執行」——各產生器每次枚舉候選數＝總額 × 分配比，下限 20%／40 個；epoch 4 收盤重算，寫進帳檔由隊長核。
- covered：公式／抽取積木的 covered＝training 中它在所有 train pair 皆取對值的題集；新積木 covered 若是既有積木子集則不入庫。

## 分線（≤3，按檔案切）

| 線 | 檔案範圍 | 介面 |
|---|---|---|
| **A：D1 每物件規則** | 新 `src/arcagi/objrule/`（對齊、擬合、執行）、`src/arcagi/blocks/gen_extract.py` 加物件視角、`aos/blocks/objrule_*`、`ext_obj_*` | 對外一個函式 `fit_objrule(task) -> list[program]`，由搜尋第一步呼叫；extract 執行器加 `scope="object"` |
| **B：D2＋D3＋D7** | `src/arcagi/blocks/pool.py` 拆成 `pool/ledger.py`、`pool/budget.py`、`pool/cli.py`；`gen_formula.py` 加 2 層與抽取特徵 | `budget.allocate(epoch) -> dict[產生器, 候選數]`，三台產生器改讀此值；A 線只依賴 ledger 分紅介面 |
| **C：D4 搜尋預算＋驗收** | `src/arcagi/search/` 常數與剪枝、評測腳本、`tests/` | 先跑一次 baseline（新常數、無 A/B 改動）確認退步 0，再合 A、B 跑最終 |

順序：C 先做（半小時）出 baseline；A、B 平行；最後 C 合流跑 training、evaluation 各一次。

## 驗收數字

- **evaluation ≥ 38/400**（+6），**同大小 ≥ 13/270**（+5），training ≥ 95/400，退步 0（有則列原因）。
- D1 抽查的 53 題 training 解出 ≥ 10；extract 積木 evaluation ≥ 2 題；公式 live ≥ 40。
- 過 train 答錯 evaluation ≤ 18（現 13；放大預算容許 +5，超過即回退 `MAX_NODES`）。
- 每題 ≤ 20 秒、全量 evaluation ≤ 15 分鐘（12 worker、nice 19）。
- 帳：epoch 4 有 extract 分紅 > 0；`generator_budget` 實際決定三台枚舉量（日誌印出）。
- `pool/` 每檔 ≤ 300 行；pytest 全綠。

## 第 6 節推薦答案

1. **範圍**：D1＋D3＋D7＋D2 半＋D4 溫和，三線如上——同大小 270 題是最大池且三輪未動，其他案都是陪襯。
2. **表示與擬合**：transform 參數欄引用 extract 積木、每物件各取值；對齊 train 物件後找「對所有物件一致」的來源；防背答案靠 ≥2 種參數值、≥3 物件——這樣不加新型、搜尋與 JSON 都不用改結構。
3. **能**：參數來源＝物件視角 extract 積木，由 `gen_extract` 枚舉、帳按被引用次數分紅——這正是「產生積木」而非手寫。
4. **公式 2 層**：先 1 層後 2 層、形式與係數白名單、上限 3000、covered 子集不入庫——枚舉量可估且不污染積木庫。
5. **預算**：單位用候選數（可重現）、下限 20%／40 個、帳自動重算隊長核——秒數受機器負載影響不穩。
6. **搜尋預算**：深度 3 不動、節點 10 萬、20 秒、尺寸剪枝、不做 C++——先用滿 Python 算力再談外接；背答案用「過 train 答錯 ≤18」硬門檻守。
7. **LLM**：本輪不碰——額度全給三條 opus 線，D5 等四型與每物件規則穩定後再量才有意義。

## 第五輪預告

- D5：20 題未解題給 aos-llm 寫四型 JSON，量 train 通過率，LLM 產出直接入帳。
- D6：同深度多解投票、學習器替代輸出。
- 若 D1 見效，推「每物件規則 2 步」（換色後移動）與 C++ 枚舉器。
- 依 epoch 4 帳重分三台產生器預算，首次驗證「元優化」有無提分。
