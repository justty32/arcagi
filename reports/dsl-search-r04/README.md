# dsl-search-r04：每物件各自規則（動作參數由物件視角抽取積木提供）讓 evaluation 解 ≥38 題、同大小 ≥13

- 指令（`systemd-run --user --scope -q -p MemoryMax=16G nice -n 19` 下跑）：
  `uv run arcagi eval --split evaluation --solver arcagi.solvers.search:solve --name dsl-search-r04 --timeout 40 --workers 10 --output artifacts/r04/dsl-evaluation.json --traces artifacts/r04/dsl-evaluation-traces.jsonl`（training 同指令換 `--split training`）；
  比較 `uv run arcagi compare r03=artifacts/r03/dsl-evaluation.json r04=artifacts/r04/dsl-evaluation.json --format markdown`；記帳 `uv run python -m arcagi.blocks.pool --report artifacts/r04/dsl-evaluation.json --epoch 4 --split evaluation`。產生器：`python -m arcagi.blocks.gen_formula`、`gen_extract`、`gen_meta`（`--split training`）。commit `9dcf110`。
- 結果：**evaluation 37/400（9.25%）**、training **92/400（23.0%）**，errors=0；同大小 evaluation **13/270**（r03 8）、training 44/262（r03 37）。每題最長 20.4 秒；evaluation 逐題耗時合計 641 秒（10 worker 牆鐘約 1～2 分鐘）。
- 基準：dsl-search-r03 evaluation 32/400、training 86/400；**退步 0**（兩個 split）。
- 結論：**部分是**——同大小 ≥13 達到；evaluation ≥38 差 1 題、training ≥95 差 3。evaluation 新解 5 題**全部來自每物件規則原語**。

## 觀察

- evaluation 新解：13713586 `extend_from(extract_713b1328)`、6ad5bdfd `move_from(extract_713b1328)`、4f537728 與 ef26cbf6 `recolor_from(extract_f23ec080)`（產生器落地的物件視角抽取積木），45737921 `recolor_from` 行內 `touching→color`。
- training 新解 6：05f2a901、2204b7a8、22eb0ac0、d43fd935、ddf7fa4f、fcb5c309（全是每物件規則）。
- 過 train 但答錯：evaluation 13（持平）、training 24（r03 22）。
- **搜尋預算不是瓶頸**：C 線 baseline（只加大預算）evaluation 32/400 與 r03 完全相同，`out_of_budget` 0/400，362 題深度 3 枚舉完；隊長另試 MAX_DEPTH=4 在 training 前 100 題 22→22、每題最長 3.3 秒——觀察等價去重後樹很小，要吃 CPU 得**擴寬參數候選**而非加深。
- 公式：抽取值當特徵＋2 層式子，live 24→35（未達 40；1 層全失敗的目標只有 30 個，2 層空間掃完最多再解釋 8 題）。公式在本輪 evaluation 無新解。
- 未解主因（A 線抽查）：每物件兩步動作（移動後補線）、斜向移動、依形狀定色。

## aos 帳（epoch 4）

- 收入 37000、守恆成立。抽取產生器分紅 0→**311.5**（每物件規則用到的抽取積木分紅回流）；formula 184.2、pred 80。
- `generator_budget`（本輪起**真的執行**，單位候選數、總額 25000）：epoch 3 決定本輪 extract 5000／formula 11993／pred 8007；epoch 4 重算為 extract 42%、formula 33%、pred 26%。
- 產生器的產生器 `_gen/_meta`：對 gen_formula 設定試 6 個變異（便宜分數＝training 可解釋題數 − 候選數/1000），最佳＝去掉 sq/div 形式（同樣 183 題、少 220 候選），已寫回 `_gen/formula` config；層數封頂 2，帳結算不把 `_gen/_*` 當產生器。
- 真退休第一次觸發：40 個 pred_*（產生器積木＋連 3 epoch 0 收入＋covered）status 改 retired。

## 下一步

- 每物件規則擴充：兩步動作、斜向、形狀→色、參數來源接公式（距離＝f(大小)）。
- 擴寬候選吃 CPU（C++ 支線）；aos-llm 小樣本；整棵樹當搜尋對象（使用者 12:56 想法）。
