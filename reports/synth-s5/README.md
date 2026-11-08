S5 合成題評分集：資料規模、背答案實驗結果、給主線的建議。支線 arcagi-S5（aos 頂層派出），2026-11-08。

← [支線清單](../../notes/rounds/支線.md) S5｜接法與重生 → [接法.md](接法.md)｜原始數字 [overfit.json](overfit.json)

## 1. 合成集

| 項目 | 值 |
|---|---|
| 題數 | 400／400 training（失敗 0，全部第一次就成功） |
| 合成 pair | 每題 24，共 9,600；加原 train 後每題 train 26～29 個 |
| 重生 | `systemd-run --user --scope -q -p MemoryMax=8G nice -n 19 .venv/bin/python scripts/synth_generate.py --workers 6`（約 5 秒，7 MB） |
| 可重生驗證 | `scripts/synth_generate.py --check 20` → 20/20 sha256 相同 |
| 參數 | seed 0、difficulty 0.0–0.5、re-arc `e5b7f1d`、Python 3.12.13、`PYTHONHASHSEED=0` |
| evaluation | 沒讀、沒合成（re-arc 只有 training 規則） |

## 2. 背答案實驗

**做法**：把現有 245 個產生積木（formula 95、pred 60、extract 90；live＋covered）的「support（在哪幾題成立）」用**產生器自己的判定**重算三次——原 train、24 個合成 pair、合成 pair 每 3 個切一份（8 份，跟真題一樣大）。一筆「宣稱」＝積木在原 train 上 support 某題。重算的原 train support 與 metainfo 一致（245 個中 242 個完全相同，3 個 formula 差在 extract 特徵）。

**對照組**：同一筆宣稱拿該題自己的原 test pair 驗（同分布、只多 1 個 pair）。

| 種類 | 宣稱數 | 嚴格：24 個合成 pair 有一個不過 | 多數：8 份小樣本過不到一半 | 對照：原 test pair 不過 |
|---|---|---|---|---|
| formula | 7,019 | 33.6% | 12.8% | 1.6% |
| pred | 866 | **81.4%** | **50.0%** | 8.5% |
| extract | 576 | 61.1% | 43.6% | 13.7% |
| **全部** | **8,461** | **40.4%** | **18.7%** | 3.1% |

- live 積木：formula 27%／24%、pred 81%／50%、extract 75%／57%（嚴格／多數）。
- 58 個積木在合成集上**一題都不剩**。
- **不是換色造成的**：re-arc 會換色、放大網格，但把宣稱依「合成 pair 是否保留原題配色」「是否沒有比原題大」分組，背答案比例差不多（pred 75～85%、formula 27～43%），所以多半是真的背答案（例：pred `size > 3`、`h < 7` 這類門檻是照原題的小物件定的）。
- 只多 1 個同分布 pair 的對照只抓到 3%：**原題範例太少，看不出背答案**——這就是合成集的用處。

**怎麼讀「背答案程度」**：保守值用「多數」欄 **約 19%**（formula 13%、pred 50%、extract 44%）；嚴格值 40% 是上限，其中一部分是 re-arc 涵蓋了原題沒出現的邊角情況。

<details><summary>重跑指令</summary>

```sh
systemd-run --user --scope -q -p MemoryMax=8G nice -n 19 \
  .venv/bin/python scripts/synth_overfit.py --out reports/synth-s5/overfit.json --preview
```
約 2 分鐘（預覽佔大部分）。`overfit.json` 的 `claims` 是逐筆（積木、題、嚴格是否過、小樣本過率、對照是否過），`blocks` 是逐積木。
</details>

## 3. 直接換成合成集評分會怎樣（預覽，未寫 aos/blocks）

用產生器原本的 judge 在 `data_synth`（原 train＋合成）上重跑一次，比 live 名單：

| 產生器 | 原本 live | 換後 live | 留下 |
|---|---|---|---|
| formula | 35 | 27 | 13 |
| pred | 60 | 38 | 12 |
| extract | 51 | 23 | 7 |

三台評分合計 11 秒 → 82 秒。

**風險**：帳上有收入的產生積木 5 個，嚴格換法會丟 2 個——`formula_0832d6a3`（`n_shape+1`，4 題全不過）、`extract_f23ec080`；`extract_713b1328`（解過 2 題 evaluation）只剩 1 題 support。直接硬換**可能讓 evaluation 退步**。

## 4. 給主線的建議（代定，主線可翻）

1. **先軟接**：分數＝原 train support 中「8 份小樣本過 ≥50%」的題數（多數欄）。這個規則下 live 的 pred 全部保留分數、formula 13 個／extract 16 個歸零。
2. **帳上有收入的積木不因合成集退休**，只降權；等跑完 evaluation 再決定。
3. 驗收照 S5：重產積木 → evaluation 全量 → `arcagi compare` 退步 0 才換。全量評測由主線排時段（本線沒跑任何評測）。
4. 建議 ledger 列（主線核後寫）：`S5 synth-overfit｜245 blocks／8,461 claims｜strict 40.4%、majority 18.7%、heldout 3.1%｜commit 見本檔 git log`。
