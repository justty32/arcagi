# dsl-search-r03：自動產生的公式型與抽取型積木，讓 evaluation 解 ≥36 題

- 指令（`systemd-run --user --scope -q -p MemoryMax=16G nice -n 19` 下跑）：
  `uv run arcagi eval --split evaluation --solver arcagi.solvers.search:solve --name dsl-search-r03 --timeout 15 --output artifacts/r03/dsl-evaluation.json --traces artifacts/r03/dsl-evaluation-traces.jsonl`（training 同指令換 `--split training`、輸出 `artifacts/r03/dsl-training.json`）；
  比較 `uv run arcagi compare r02=artifacts/r02/dsl-evaluation-b.json r03=artifacts/r03/dsl-evaluation.json --format markdown`；top-2 `uv run python scripts/score_top2.py <報告>`；記帳 `uv run python -m arcagi.blocks.pool --report artifacts/r03/dsl-evaluation.json --epoch 3 --split evaluation`。產生器：`python -m arcagi.blocks.gen_formula --split training`、`python -m arcagi.blocks.gen_extract --split training`。
- 結果：**evaluation 32/400（8.0%）**、training **86/400（21.5%）**，errors=0；每題最長 3.8 秒，全量 evaluation 約 210 秒（逐題耗時合計）。top-2 與 top-1 相同。
- 基準：dsl-search-r02 evaluation 28/400、training 79/400；**退步 0 題**（兩個 split）。
- 結論：**否**（fable 驗收 evaluation ≥36、尺寸隨輸入 54 題 ≥8、同大小 ≥11、training ≥95 都沒達到）。但 evaluation 新解 4 題**全部來自自動產生／擬合的公式型積木**，方向成立。

## 觀察

- evaluation 新解：a59b95c0 `tile_n(n_color+1, n_color+1)`、d4b1c2b1 `upscale_n(n_color+1, …)`（這兩題是搜尋時直接擬合的式子）、ccd554ac `tile_n(formula_fbe415b1×2)`（`w`）、e872b94a `canvas(formula_0832d6a3, 1, 0)`（輸出高＝某個特徵）——後兩題用的是產生器落地的積木。
- 切片：「尺寸隨輸入、非簡單倍數」54 題 2→6；同大小 8→8（背景修正在 evaluation 沒轉成新解）；輸出變小 16→17；其他 4→7。
- training 新解 7：公式 4（2dee498d、ac0a08a4、b91ae062、d631b094）、抽取 1（0b148d64 `crop_extract`）、背景修正 2（67385a82、aedd82e4）。
- 過 train 但答錯：evaluation 13（r02 12）、training 22（r02 20）。投票與尺寸提示沒有實際改動任何 top-1（`shape_hint_applied` 全 0）；top-2 仍無增量——第一個有解的深度幾乎只有一種輸出。
- 抽取積木在 evaluation 沒有解出題；產生器 44 live。
- C 線抽查 training 那 53 題「謂詞分得開但沒解出」：多數是各 pair 方向不同的移動、混色重繪、換成鄰近物件顏色，單一「選擇器＋動作」做不出來，不是缺謂詞或背景。

## aos 帳（epoch 3）

- 收入 32000、守恆成立。產生器：`_gen/formula` 分到 186.7（花費 0.6），`_gen/pred_combiner` 80，`_gen/extract` 0（花費 8）；`generator_budget` 建議（只記不用）formula 48%、pred 32%、extract 20%（底線）。
- essential 13 個（8 幾何＋5 物件選擇器）不再出現在建議退休；建議退休 10 個（含 4 個巨集、local_rule、gravity）。
- 真退休 0：條件是「產生器積木＋連 3 epoch 0 收入＋covered」，pred_* 從 epoch 2 才出生，還沒滿 3 個 epoch。
- 施工中發現 pool 只把 `pred_*` 參數算成積木引用，`formula_*`／`extract_*` 沒算 → 隊長修正後重記 epoch 3（未提交的錯帳已回復）。

## 下一步

- 同大小 270 題仍是最大池：需要「多規則並存」與物件互動（移動方向依物件而定、依鄰近物件換色）的表示，不是單一選擇器＋動作。
- 公式與抽取組合（抽取值進公式、公式定參數）；抽取積木要接到更多動作才會有收入。
- 投票要有效得讓搜尋在有解深度之後多看一層，或讓不同學習器產生不同輸出。
