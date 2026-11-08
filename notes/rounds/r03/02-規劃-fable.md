第三輪規劃：fable 只讀 [01-簡報](01-簡報.md) 一次性產出，以下原樣存檔（隊長未改字）。

← [交棒總表](../README.md)｜上一步 [01-簡報](01-簡報.md)｜下一步 [03-設計](03-設計.md)

# 第三輪規劃（fable）

## 範圍
落實「積木＝模式，不只幾何」：施工公式型、抽取型兩個產生器並接進搜尋；順手修物件背景、同深度多解投票、補帳；LLM 延後。

## 求解器與積木方法
- **特徵層（新）** `features.compute(grid)→{h,w,n_obj,n_color,max/min_obj_h/w,n_bg,n_fg,n_shape,cnt_c…}`，公式與抽取共用。
- **公式型產生器 `gen_formula`**：目標 h_out、w_out、重複次數 n；式子＝`a·x+b`（a 1～4、b −3～3）、`x·y`、`x²`、`max/min(x,y)`、`x/k` 整除；≤1 個運算、≤2 個特徵。評分＝training 上「所有 train pair 成立且特徵值 ≥2 種」的題數；0 題不落地；被常數更少的式子解釋其支持集 → covered。
- **抽取型產生器 `gen_extract`**：式子＝選擇器（重用 pred_*、largest／smallest／unique 色或形）×屬性（bbox、color、size、count、cells）；評分＝training 上「抽出值等於輸出某屬性（輸出＝裁框、輸出色集＝該色、h_out＝計數）」題數；落地／covered 同上。
- **接進搜尋三路**：(a) 尺寸剪枝：每題先用 train 擬合 h_out/w_out，能擬合且非同大小者，中間層尺寸不可達即剪；(b) 新生成原語 `canvas(h=$formula,w=$formula,color)`、`crop($extract:bbox)`、`tile(n=$formula)`、`fill($extract:color)`，參數來自式子而非常數；(c) 防背答案：式子解題時逐題重擬合，擬不上就不用。
- **物件背景**：同題一致＝所有 train 格共同眾數，平手取邊框色；謂詞選擇器動作擴到 keep／delete／recolor／move_to_edge。
- **選解**：到首個有解深度後收完該深度（上限 200 解），按測試輸出分組；top-1 仍最短（平手取票多），top-2 取票最多的不同輸出；學習器解權重 0.5。

## aos 接入
- 新節點 `aos/blocks/_gen/formula`、`_gen/extract`；落地積木 `formula_*`、`extract_*` 資料夾，`_metainfo` 記分數、支持題、covered_by。
- 帳（epoch 3）：`essential:true` 名單（隊長手列：8 個基礎幾何＋物件選擇器，永不退休）；巨集分紅 50% 按展開下傳成分；產生器記成本（耗秒×費率）與收入（抽分紅 20%）；真的執行退休，僅限自動產生、連 3 epoch 0 且 covered 者，移到 `retired/`；帳末輸出各產生器下輪預算建議（按淨收入比例、底線 20%），本輪只記不用。

## 分線（≤3 條，各 1～1.5 h）
- **C 線**：先 20 分鐘交 `src/arcagi/objects/background.py`（A、B 依賴），再做謂詞動作、`search/vote.py`、`aos/pool/` 帳改。
- **A 線**：`src/arcagi/features/`、`formula/`、`blocks/gen_formula.py`、搜尋尺寸剪枝；介面 `formula.fit(pairs,target)→Formula|None`、`Formula.eval(grid)→int`。
- **B 線**：`src/arcagi/extract/`、`blocks/gen_extract.py`、執行器 `$extract:` 解析、四個生成原語；介面 `extract.run(expr,grid)→json`。
- 合併後全量 training 一次，再 evaluation 一次。

## 驗收
- evaluation ≥36（目標 40），已解 28 題退步 0；「尺寸隨輸入」54 題 ≥8；同大小 ≥11。
- training ≥95（目標 105）；過 train 答錯 ≤12。
- 每題 ≤5 秒、全量 evaluation ≤400 秒；機器限制照舊。
- pytest：特徵、公式擬合、抽取、背景色、投票各有測試，全綠。
- aos：`aos-exec` 可單叫兩個產生器；pool epoch 3 看得到產生器成本／收入、essential 旗標、≥1 個 pred_* 真退休、formula_*／extract_* 各 ≥5 個 live。

## 第 6 節推薦
1. 範圍：C1＋C2＋C3 為主，C4、C5 輕量，C6 延後，C7 只記不決——主軸是產生器，額度只夠三線。
2. 產生器如上；深度 1 運算即可，空間小、可全枚舉、好解釋，且 54 題池多是一階關係。
3. 背景做同題一致＋四個動作，extend 下輪——53 題卡點是動作缺，不是選擇器。
4. 收完該深度、不多一層，top-1 仍最短——多一層費時，背答案主因是學習器，降權即可。
5. essential 由隊長手列入檔、巨集分紅下傳、產生器記成本；真退休限自動積木——手寫積木退休無收益只有風險。
6. LLM 不碰——額度緊，且四型執行器完工後下輪才有乾淨的未解題池可量通過率。
7. 元優化推到「帳算出預算建議」即止，實際分配留第四輪——先驗證數字合理再放權。

## 第四輪預告
帳的產生器預算真正執行；公式／抽取深度 2 與互相組合（抽取值進公式）；C6 用 LLM 對剩餘尺寸隨輸入題寫四型 JSON、量通過率；若算力成瓶頸再開 C++ external。
