# think-4 progress（先修量尺再演化）

主題：①修快撥量尺（C25 auc_L 全 20）②演化缺口（交配同 sha、D27、D18）③塊 5 Janet＋節點池。流程見 `../思考輪-流程.md`。

## 第一棒（t4 隊長）

- [完] 01a 蒐集（codex sol 唯讀，`arcagi-t4-gather`，26 KB）。
- [完] 01-簡報：隊長親查 auc_L=20 根因＝**5 題從 e0 就由庫存積木命中、11 題 25k 內永不解，5×4=20**；尺量的是庫存不是學習。另更正：D27、D18 已接線，缺的是對照證據。
- [完] 02 fable（10 KB）：剝庫量學習、主分 learn_bits、題集 L′、6 棵改笨樹、顯著門 |z|≥2＋兩半同號、meter.py/dumb.py/cli。
- [完] 02b Argon（18 KB，無 auth 錯）。至少兩條 P0：①learn_bits 不扣 e0、e0 靜態解題重複領 4 次分→主體仍量靜態搜速非跨輪學習；②L′ 取 P48 最易 10 題→剝庫後要嘛免學即解、要嘛全掛。
- [完] 代定清單 T1–T7（照 fable 推薦）。

## 下一步（第二棒）

1. 讀 `02b-Argon審.md` 全文（18 KB，用 grep／分段），逐條在 `代定清單.md` 標「維持／改」——P0 ①② 必回應（T2 主分可能改「扣 e0 的跨輪增量＋e0 靜態分分列」；T4 選題改邊緣題梯度）。
2. 寫 `03-設計.md`（塊 A 量尺：meter.py／dumb.py／quick.py 改點／cli meter、dumb、meter-batch、meter-accept；驗收寫死含「≥3 改笨樹顯著、judge-high 不顯著、≥1 個 g1 子代顯著」）。
3. 施工交 codex sol（`-m gpt-6.1-sol -s workspace-write -C /home/lorkhan/repo/arcagi --add-dir /home/lorkhan/code/playground-arc1/ws/evo`），任務書帶本夾安全邊界；隊長審 diff→實跑（systemd-run arcagi-t4-<名>，worker ≤4）→ commit → `04-總結簡報.md`。
