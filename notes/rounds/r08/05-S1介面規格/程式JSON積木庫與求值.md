← 入口 [05-S1介面規格](../05-S1介面規格.md)

## 2. 程式 JSON（`interp.to_json`／`from_json`）

| 形式 | JSON | 意義 |
|---|---|---|
| 整數字面值 | `3`、`-1` | 常數葉子 |
| 輸入 | `["$in"]` | 該題（或子目標）的輸入值；任何深度都看得到 |
| lambda 參數 | `["$0"]`、`["$1"]` | **最內層** lambda 的第 0／1 個參數 |
| lambda | `["lam", n, body]` | n ∈ {1, 2}；n 是 JSON 整數 |
| 原語呼叫 | `["add", a, b]` | 名稱必須在 PRIMS 裡，參數數量要對 |
| 積木 | `["blk", name, a0, a1]` | 積木庫的積木，參數依序填進洞 `$h0`、`$h1` |
| 子目標葉子 | `["$u"]`、`["$v"]`、`["$i"]` | 只會出現在 §7 的子目標裡（值由呼叫方給）；組回整支程式後就不會再出現 |

- **lambda 環境不疊加**：進入內層 lambda 時，參數環境整個換成內層的參數，所以內層看不到外層的 `$0`、`$1`（`$in` 還是看得到）。例如 `["zipwith", ["lam", 2, ["zipwith", ["lam", 2, ["max", ["$0"], ["$1"]]], ["$0"], ["$1"]]], A, B]`：外層 lambda 的 `$0`、`$1` 是兩列，內層的 `$0`、`$1` 是兩個元素。
- **大小**（`interp.size`）：葉子算 1；原語呼叫算 1 加上各參數的大小；lambda 本身不算，只算 body；`blk` 算 1 加上各參數的大小（不展開）。

## 3. 積木庫 `blocks.json`（`seed.library`）

- 檔案是 JSON list，每個元素 `{name, body, sig, src_tasks, saving, uses}`（grow 另外加了 `born`、`holes`、`idle`，讀的時候忽略）。
- `body` 是程式 JSON，可以含洞 `["$h0"]`、`["$h1"]`。`sig`：有 k>0 個洞時，是 k 個參數的函式型別（參數就是洞的型別，回傳是積木的型別）；沒有洞時就是積木本身的型別，可能是函式型別（這時積木當 lambda 用）。
- **展開是語法替換**：先把 `blk` 的參數程式代進洞，再求值。所以洞如果在 lambda 裡，填進去的程式可以引用那個 lambda 的參數。r07 實例 `d10ecb37`：`["map", ["lam", 1, ["blk", "g1_0fe6fca1dc", ["$0"]]], …]`。
- 枚舉只用 body 裡沒有自由 `$0`／`$1` 的積木（在積木自己的 lambda 之外）。有洞的積木當運算子（ops），沒洞而且不是函式型別的當葉子，沒洞而且是函式型別、參數型別剛好相符的，當大小 1 的 lambda。子目標（sub）另外排除兩種積木：body 用到 `$in` 的，和有洞在 lambda 裡的（`decomp.sub_library`）。

## 4. 求值語意（`seed.interp`）

- 每次原語呼叫扣 1 步。上限 `MAX_STEPS = 200000`，超過就丟 `EvalError`。字面值、`$in`、`$k`、lambda 建構都不扣步。
- 所有失敗都變成 `EvalError`（JSON 輸出寫 `"ERR"`），包括：空 list 取 `head`、`nth` 越界或負索引、`mod` 除以 0、型別不合（例如對整數取 `len`）、超出資源上限。
- 資源上限：list 長度超過 `MAX_LEN = 1024` 時 `cons`／`append`／`concat`／`range`／`repeat` 會丟錯；`add`／`sub`／`mul` 的結果超出 ±`MAX_INT = 10**9` 時丟錯（`neg`、`mod` 不檢查）。
- 整數語意照 Python：`mod` 是 floor mod（`-7 mod 3 = 2`、`7 mod -3 = -2`）；`sort` 的順序是 Python 的全序：整數照大小、list 照字典序、布林 False < True；`eq` 是深層相等。
- 32 個原語的型別簽名在 golden 檔的 `sigs` 欄位。每個原語的邊界語意（ragged 的 `transpose` 跟 Haskell `Data.List.transpose` 一樣：跳過太短的列；`take`／`drop`／`range`／`repeat` 的負數當 0；`fold f z xs` 的 `$0` 是累積值、`$1` 是元素）都以 golden 為準。
- **golden**：`tests/seed/golden_prims.json`，每個原語 20～30 組，共 747 組，含 ragged、負數、空 list、溢位、ERR。每組是 `{program, input, output[, args]}`：`program` 是只用到這一個原語的整支程式（整數參數寫成字面值；list／bool 參數從 `$in` 取，只有一個就是 `["$in"]` 本身，多個就用 `["nth", ["$in"], j]` 取；函式參數寫成 lambda），`input` 是 `$in` 的值，`output` 是值或 `"ERR"`；一階原語另外附 `args`（參數值）。C++ 必須全部通過。重產指令：`uv run python tests/seed/make_golden_prims.py`（`tests/seed/test_golden_prims.py` 會驗證檔案和 Python 一致）。

## 5. 整數字面值（`prims.task_consts`）

葉子整數＝{0, 1, −1} ∪ 例對（輸入與輸出）中出現的每個整數 ∪ 每個巢狀 list 的長度，排序後去重。整題模式由 train 的輸入和輸出算；子目標模式由呼叫方直接給 `consts`（Python 用整題的 consts，不是子目標的）。

