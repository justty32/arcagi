第九輪 B 線：`hammer/sieve.py` 兩種篩的掃描結果。判準照 [03 §4 提案 3](../../../notes/rounds/r09/03-設計.md)，寫在 `sieve.py` docstring，跑之前寫死。程式只讀 taskset 的 `learn`（L16）與 `P48`，不載入 H8／H24 題號。

## 1. sieve/exclude：32 原語逐一留一

- 設定：arcbatch `--mode seed`，budget 100k，`decomp: true`（C++ 七拆法），`lam_depth 2`，空庫；33 個設定（base＋32 個 `exclude:[p]`），64 題（L16＋P48），8 執行緒，牆鐘 6.4 秒。重驗用全部原語。
- 兩折：`sha1(task_id+"r09AB")` 末位偶數＝A（34 題）、奇數＝B（30 題）。base 解出 A 12 題（Σnodes_to_first 291,126）、B 5 題（14,200）。
- 門：A 折 0 掉題且 Σnodes_to_first 降 ≥5% → 選中；B 折折外 0 掉題且降 ≥5%（或多解 ≥1）→ 接受（進 `incubating`）。

| 結果 | 原語 |
|---|---|
| A 折選中 | `len`（A 降 5.6%）、`range`（16.6%）、`repeat`（5.4%） |
| B 折折外接受 | **0 個**：`len`、`range` 在 B 各掉 1 題；`repeat` B 0 掉題但只降 3.5% |
| A 折就掉題 | `if`、`take`、`reverse`、`append`、`sort`、`map`、`transpose` |
| 0 掉題、降不到 5% | 其餘 22 個 |

- 讀法：A 折選中、B 折被擋，正是兩折設計要防的「在選的那半過擬合」；三個候選都只是 A 折幾題剛好不用該原語。逐題數字在 [exclude.json](exclude.json)。
- 本次只掃不寫：活樹 `ws/hammer/` 不是 B 線碰的；`sieve.write_exclude(root, res, epoch)` 會對每個試過的原語寫一筆 ledger（`layer:2 by:gate-scan`，`accepted` 照實），接受者寫 `kind:sieve status:incubating` 列，由隊長或 epoch 的 `rt_gatescan` 對活樹呼叫。

## 2. sieve/equiv：探針等價類（只挖不用）

- 5 張 4×4 隨機探針（`random.Random(9)`），列舉 size ≤3 的一階程式（葉＝`$in`、−1、0、1、2、3；一元＋二元原語，不含 lambda／HOF），共 1,278 支；用 `grow.sig.infer_sig` 濾掉不合型別的（`seed-run` 是動態求值，不擋型別），剩 343 支；`arcbatch --mode seed-run` 算值，非全 ERR 的 333 支。

| 量 | 值 |
|---|---|
| 合型別、有值的程式 | 333 |
| 觀測等價類 | 77 |
| 估計可剪比例（不是該類第一支的） | **76.9%** |

- 最大的幾類：常數 0（`0`、`(neg 0)`、`(len (range 0))`… 50 支）、恆假（`(eq 0 1)`… 35 支）、常數 1／2／−1／3、空串（`(range 0)`、`(reverse (range 0))`…）、恆真（`(eq $in $in)`…）。全表在 [equiv.json](equiv.json)。
- 注意：枚舉器本來就用觀測等價去重（bank 以值為鍵），所以這 77% 不是「省下的搜尋節點」，而是「先生成、求值後才丟掉」的那部分；C++ 端若能在生成前用 `forbid` 擋掉（`(neg (neg x))`、`(reverse (range c))`、`(eq x x)` 這類），省的是求值與雜湊。數量級要等 S1 實作後量。信稿：[S1信稿.md](S1信稿.md)（隊長寄）。

重跑：`uv run python -m arcagi.hammer.sieve exclude --work DIR`、`uv run python -m arcagi.hammer.sieve equiv --work DIR`。
