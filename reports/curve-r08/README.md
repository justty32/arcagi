# r08 學習曲線（B 線：練習池、迭代加深、logcost_L、5-seed CRN meta）

**結論**：練習池這一輪**沒有讓曲線動起來**。主樹 `pool`（分解 DEFAULT＋G1＋主題練習池 P32，seed `b67dc2a`）的 AUC_L 是 32、Δ_L 0，跟 r07 對照 `dec-g1`（32）一樣，也跟不學的 `pool-noG1`（32）一樣。原因是主題 P32（`draw.ring_around`、`objects.copy_stamp`、`pattern.make_symmetric`、`overlay.boolean`）在 25k～400k 預算下 0 題過 train，`clean_P` 全 0，G1 沒有料可學，冷啟動死鎖照舊。

改成按空樹立足點挑主題的 `pool-foot32`（D-r8-18）以後，練習池第一次真的吐出料：`clean_P` 10→15，`false_pos` 0，長出 8 個 P 積木，`reverse $in` 被 L16 用了 8 次，`transpose $in` 被 6 題共用，H24 1→2。但同時 L16 少解 1 題（beb8660c），AUC_L 降到 26，反而比較差。

5-seed CRN meta 跑了 5 回合，全部不採用；拆法動作 `halves`、`nest` 也都不採用。halves 讓 L16 從 4 題升到 6 題（AUC_L 12→18，5 個 seed 都一樣），但 H24 不動，跨題 bootstrap 的判準也沒過（降幅 20.3 < 2×SE 25.8）。H8 全程 0，`llm_calls` 全 0。

<!-- wf-nav -->
以下章節按語意拆到同資料夾的子檔，原文照搬：
- [指令；題組（`data/r08/taskset.json`，sha1 `418234a6748e3f4ed13ecffd6a2e7aa8be98efa9`）](指令與題組.md)
- [曲線（solved 欄是 pass 0..8）；每主題（P 內，最後一個 pass：過 train／過 G1 門／test 對）](曲線與每主題.md)
- [門：舊門（MDL /4）跟新門（MDL /1）各擋掉哪些題；seedlib 積木（來源 P／L）](門與seedlib積木.md)
- [meta（4-pass、P 封頂 100k、CRN seeds 1..5、`pool` 設定不開 G4）；雜訊](meta與雜訊.md)
- [門檻（D-r8-11、規劃 §5）；偏置與限制](門檻偏置與限制.md)
