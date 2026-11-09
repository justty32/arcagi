# S1 `forbid`：seed 列舉的 AST 樣式剪枝，開／關對照

## 白話

照 S1 規格做好了 `forbid`：arcbatch `--mode seed` 的設定行可以帶一串 AST 樣式（`?x` 代表任意子程式，同名出現兩次就必須是同一支；`?c` 代表任意整數常數）。列舉器組出新程式時，如果根部符合任何一條樣式，就**在求值前**跳過：不算節點、不進 bank，跳過的次數記在 `forbidden` 欄。沒給 `forbid` 時，輸出跟舊的 `bin/arcbatch` 逐欄相同（有測試）。

結果：**解集合完全一致，但速度沒有可量到的提升。** 規格那 9 條樣式只擋到 0.5–1.4% 的候選，再加 10 條冪等樣式（fb2）也只擋到 1.3–3.1%。被擋的幾乎全是「值跟某個子項一樣」的程式，本來就會被 bank 去重丟掉，所以省下的只有這 1–3% 的求值成本，比計時雜訊（同組重跑差 ±5%）還小。r09 探針說的「77% 是等價重複」大多不是這種根部兩層的樣式能抓到的；要真的省，得換成更大的探針挖掘樣式集，或把列舉搬上 GPU（見 `seed-gpu-可行性.md`）。

## 設定

- 題目：training 依檔名排序的前 100 題，`--mode seed`，`decomp: true`，4 執行緒；同時有其他 GPU 長跑（共用機器計時）。
- `base`：不給 forbid。`fb`：規格信裡的 9 條。`fb2`：9 條＋10 條冪等（`sort∘sort`、`max/min/and/or ?x ?x`、`mul 1`、`sub ?x 0`、`len∘reverse`、`len∘sort`）。全文見 `patterns.json`。
- 預算掃描各跑一次，用第一版比對器；計時重複組用改過的版本（每個 op 先建好適用樣式清單），語意相同，被擋數逐位相同。

## 預算掃描（一次跑）

| 預算 | 設定 | 求值節點 | 被擋 | 被擋% | task 秒 | 節點／秒 | 含被擋的候選／秒 | train 對 | test 對 | 共同解題的到解節點合計 | 到解秒合計 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1e5 | base | 9,576,278 | 0 | 0 | 2.54 | 3.76M | 3.76M | 4 | 4 | 121,171 | 0.021 |
| 1e5 | fb | 9,575,887 | 132,656 | 1.37 | 2.67 | 3.59M | 3.64M | 4 | 4 | 120,780 | 0.028 |
| 1e5 | fb2 | 9,575,662 | 310,363 | 3.14 | 2.83 | 3.39M | 3.50M | 4 | 4 | 120,555 | 0.030 |
| 1e6 | base | 92,571,392 | 0 | 0 | 35.80 | 2.59M | 2.59M | 7 | 5 | 965,021 | 0.154 |
| 1e6 | fb | 92,570,740 | 573,087 | 0.62 | 42.40 | 2.18M | 2.20M | 7 | 5 | 964,369 | 0.234 |
| 1e6 | fb2 | 92,570,296 | 1,624,235 | 1.72 | 38.58 | 2.40M | 2.44M | 7 | 5 | 963,925 | 0.236 |
| 1e7 | base | 895,292,707 | 0 | 0 | 528.25 | 1.69M | 1.69M | 10 | 7 | 8,682,747 | 2.006 |
| 1e7 | fb | 895,285,026 | 4,107,747 | 0.46 | 463.52 | 1.93M | 1.94M | 10 | 7 | 8,675,066 | 1.797 |
| 1e7 | fb2 | 895,282,567 | 12,210,738 | 1.35 | 557.92 | 1.60M | 1.63M | 10 | 7 | 8,672,607 | 1.975 |

單次跑的秒數在 ±15% 內亂跳（1e6 fb 較慢、1e7 fb 較快），方向不一致，所以看下面的重複組。

## 計時重複（預算 1e6，三組交錯各 3 次）

| 設定 | 次數 | task 秒中位數 | 最小..最大 | 求值節點／秒 | 含被擋的候選／秒 |
|---|---|---|---|---|---|
| base | 3 | 35.90 | 33.43..35.96 | 2.58M | 2.58M |
| fb | 3 | 36.67 | 36.20..36.67 | 2.52M | 2.54M |
| fb2 | 3 | 33.75 | 30.59..34.11 | 2.74M | 2.79M |

差距 −2%～+6%，落在雜訊裡（base 自己就有 33.4–36.0 的落差；第 1 輪跟 pytest 同時跑）。理論上限就是被擋比例：fb 約 0.6%、fb2 約 1.7%。

## 解集合一致性

- 三個預算下，fb、fb2 跟 base 的 train 對集合、test 對集合、**每題找到的程式**完全相同（0 題不同、0 題消失、0 題新增）。
- base 在 1e7 train 對的 10 題：1e0a9b12、1fad071e、22eb0ac0、239be575、25d8a9c8、25ff71a9、27a28665、2dee498d、3c9b0459、445eab21（test 對 7 題）。
- 到解節點：有被擋的題目，減少的數量剛好等於到解前被擋的數量（例：1e7 的 1e0a9b12 196,491 → fb 191,896 → fb2 190,772；2dee498d 124,282 → 121,740 → 120,771）。其他題（例 445eab21 4,873,501）三組相同，因為解出現在拆解後的子問題，到解數落在子預算邊界上。
- 為什麼不掉題：大多數樣式的值等於某個子項的值，那個值已在 bank 裡，原本也會被去重，所以 bank 內容不變。規格裡 `reverse(range ?c)`、`eq ?x ?x`、`len(range ?c)` 不屬於這類（值可能是新的）；這 100 題沒因此掉題，但大題組要再確認。

## 實作要點

- `native/src/seed_enum.cpp`：thread-local 樣式清單；`Enumerator` 建構時對每個 op 先挑出頭符號與元數相符的樣式；`emit` 在求值前只對有適用樣式的 op 做比對（不組整棵樹，直接拿子項目的程式比）。區塊 op 用 `["blk", 名稱, ...]` 樣式。
- `native/src/seed_main.cpp`：設定行讀 `forbid`；每題 solve 前後 `set_forbid`／`forbid_count`；有 forbid 時每列與 summary 多 `forbidden` 欄。
- 沒套 forbid 的地方：lambda 體池（BodyPool）跟 cond 見證；只擋主列舉器的根。
- 新 binary：`make -C native forbid` → `native/bin/arcbatch-forbid`（全部原始碼編成一支 arcsearch，用法要帶 `--batch`）。沒重編 `bin/arcsearch`、`bin/arcbatch`，沒動 `native/gpu/`。

## 測試

`uv run pytest -q tests/native`：21 passed（原本 17＋新 `tests/native/test_seed_forbid.py` 4 個：不給 forbid 時 decomp 開／關都跟舊 `bin/arcbatch` 逐欄相同；等價樣式下程式不變，而且「到解節點＋被擋＝base 到解節點」；萬用字元語意）。

## 重跑

```sh
make -C native forbid
ls data/ARC-AGI/data/training | sort | head -100 | sed 's/.json//' > train100.txt
# cfg-1000000.jsonl：三行 base／fb／fb2，forbid 取 patterns.json 的 spec、spec+extra
systemd-run --user --scope --unit=arcagi-n5-bench -p MemoryMax=12G nice -n 19 \
  native/bin/arcbatch-forbid --batch --mode seed --tasks train100.txt --configs cfg-1000000.jsonl --threads 4 > res-1000000.jsonl
uv run pytest -q tests/native
```

原始 jsonl 與分析腳本（不 commit）在 scratchpad `/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n5/`（`res-*.jsonl`、`tim-*.jsonl`、`analyze.py`、`analysis.md`）。
