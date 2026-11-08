第九輪 B 線：鑄模廠 `hammer/foundry.py` 管線驗通。用一個**回放測試蠟模**（B 線手寫、`"by":"test-replay"`）跑 `ingest`，看蠟模能不能經逐段擬合、常數抽槽、段殘差門變成 `comb incubating` 列。

> **測試蠟模不計 M2(c)。** 它是 B 線照題目手寫的軌跡，只用來驗管線；產出的列 `evidence.test_replay = true`、ledger `test_replay: true`、LLM 稅記 0。真蠟模由隊長另派。

## 蠟模

- 題：`67e8384a`（P48，3×3 → 6×6 雙向鏡射，4 對 train）。檔案：[test-wax-67e8384a.jsonl](test-wax-67e8384a.jsonl)。
- 三步：`mirror_rows`（每列接自己的反轉，3×6）→ `flip_v`（上下翻）→ `stack_flip`（翻回來疊上去，6×6＝output）。

## 結果（`arcbatch --mode seed-sub`，budget 200k，空 live 庫）

| 段 | tag | 擬合程式 | info_bits | prog_bits | diff_bits | loo | 門 | 產出列 |
|---|---|---|---|---|---|---|---|---|
| 0 | mirror_rows | `(map (lam1 (append $0 (reverse $0))) $in)` | 126.2 | 38.0 | 239.2 | 過 | 過 | `comb_fd_67e8384a_0` |
| 1 | flip_v | `(reverse $in)` | 126.2 | 10.9 | 119.6 | 過 | 過 | `comb_fd_67e8384a_1` |
| 2 | stack_flip | `(append (reverse $in) $in)` | 252.5 | 21.7 | 478.4 | 過 | 過 | `comb_fd_67e8384a_2` |

- 三列都是 `kind:comb status:incubating by:foundry`，簽名 `list[list[int]]`，0 槽（程式裡沒有題目常數）；斷裂面 0 段；`frozen.json#/priors` 加三筆（38.0＋10.9＋21.7 位元）；ledger 一筆 `kind:foundry event:ingest`，`evals.foundry`＝517,322 節點（含 LOO 重搜），`llm_tax`＝0。
- `python -m arcagi.hammer.check` 對 ingest 後的樹 0 錯。
- 常數抽槽另有單元測試（`(repeat 7 …)` → 槽 `$h0`）；跨蠟模反合一（`upgrade`）本輪只有一個蠟模，沒觸發。
- 選題 `pick_task` 在新樹（還沒有 epoch 解，L16 全當未解）選出 `b27ca6d3`，`request` 寫了請求檔（只含 train 對）；那是給真蠟模用的，這裡不解。

重跑：`uv run python -m pytest -q tests/hammer/test_b_foundry.py`；或 `python -m arcagi.hammer.foundry ingest <root> <wax>`。
