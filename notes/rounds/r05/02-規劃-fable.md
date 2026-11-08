第五輪規劃：fable 讀 01 簡報後定案。

← [01 簡報](01-簡報.md)｜下一步：隊長派 3 條線、合併後跑全量、寫 03/04。

## 1. 結論先

本輪做 **E1＋E6（合併成「子樹即積木」一線）＋E2（併 E5）＋E4**；**E3 整輪不做**。理由：額度只有 3 opus 小時，分數最確定的來源是「近失敗 109 題的鄰域改寫」（E2）與「同大小 13/270 的兩步規則」（E4），兩者檔案互不重疊、可並行。E5「放寬參數候選」本質是 E2 的一條改寫規則（參數→鄰值），併入不另開線。使用者 13:09「呼叫鏈當原始碼、`$ref` 折疊」與 13:13「子樹也是積木」是同一件事兩面：子樹＝一段可 `$ref` 的原始碼，折成 `$ref` 後它就是一塊 `m_*` 巨集資料夾，進 node-pool 記帳分紅、可被改寫搜尋取用——所以 E1 與 E6 合成線 A。E3 的分數訊號（帳本分紅）要等一個 epoch 全量評測，本輪只跑一次全量、無樣本可調；改為讓 E2 記錄「每條改寫規則命中帳」、線 A 讓子樹積木進帳，給 r06 當分紅資料。aos-llm、C++ 引擎照舊留支線。

## 2. 分線（3 條，各 1 opus、約 1 小時）

### 線 A：srcspace 變換層＋子樹即積木（E1＋E6）
- 目標：積木 JSON（程式 `[[原語,參數…],…]`、巨集 `m_*/program.json`、四型 `_rule.json` body）⇄ janet S 式文字，雙向無損；在 training 解出程式與積木 body 上挖多題共用子樹，折成 `$ref`，落成新巨集資料夾。
- 可寫：`src/arcagi/srcspace/`（新建；`emit.py`、`parse.py`、`fold.py`、`subtree.py`、`promote.py`、`janet_bridge.py`，每檔 <300 行）、`tests/test_srcspace*.py`、**新建** `aos/blocks/m_sub_*/`（只准新增資料夾、上限 10 個，不改既有積木）、`notes/rounds/r05/03a-線A.md`。**不碰** `solvers/`、`objrule/`。
- 交付介面：`to_janet(obj) -> str`、`from_janet(text) -> obj`；`fold_refs(obj, macros)`／`unfold_refs`；`shared_subtrees(programs, min_tasks=3) -> list[(subtree, task_ids)]`；`promote(subtree, name) -> 寫 m_sub_*/program.json`（走既有巨集載入器格式，自然進 node-pool 記帳）；`janet_bridge.check(text) -> bool|None`（無 janet 回 None 不報錯）。
- 驗收：365 積木＋training 解出程式（≥92）往返 **100% 不變**（含 `$ref`⇄`defn`）；janet 存在時 emit 文字 `janet -e` parse 全過；挖出 ≥3 個合格子樹（≥3 題共用、不含題專屬常數）落成 `m_sub_*`；折疊後 training 解出程式總節點數下降（寫出數字）；此線不進求解路徑，評測時間不變。

### 線 B：原始碼空間改寫搜尋（E2＋E5，Python 引擎）
- 目標：BFS 失敗後，從近失敗／過 train 程式出發，在 S 式 JSON 上套改寫規則，只驗 train。
- 可寫：`src/arcagi/solvers/rewrite.py`、`solvers/rewrite_rules.py`、`solvers/rewrite_ledger.py`、`tests/test_rewrite*.py`、`solvers/search.py` **只准加一個呼叫點**、CLI 加 `--rewrite/--no-rewrite`、`notes/rounds/r05/03b-線B.md`。
- 改寫規則（固定表，各一函式）：參數→候選集鄰值（即 E5：鄰色、全色、更多 conn、±1 偏移）；同型原語替換；插一步／刪一步；交換相鄰兩步；子樹→既有巨集 `$ref`（用現有載入器，執行時自動含線 A 的 `m_sub_*`，開發期不依賴線 A）；末端接每物件規則。
- 交付介面：`rewrite.search(task, seeds, budget) -> list[Program]`；`rewrite_ledger` 每題記「哪條規則、哪個巨集、幾次命中」寫入 traces JSON。
- 驗收：evaluation 近失敗 ≥0.9 的 109 題中**新增 ≥4 解**；training 新增 ≥6；改寫程式「過 train 答錯」率 ≤ BFS 的 2 倍；每題牆鐘 ≤8 s、候選 ≤3000；全量 evaluation 總時間 ≤ r04 ×1.5。

### 線 C：每物件規則擴充（E4）
- 目標：兩步（move 後 extend、recolor 後 move）、8 方向、依形狀定色（正規化遮罩 hash → 色表）、距離＝f(大小) 以公式積木當參數來源。
- 可寫：`src/arcagi/objrule/`（**除 `objrule/families/`**）：`two_step.py`、`shape_color.py`、`param_source.py` 新檔，`rules.py` 只加註冊；`tests/test_objrule*.py`、`notes/rounds/r05/03c-線C.md`。不碰 `solvers/`。
- 交付介面：每物件規則註冊表新增 4 個規則名，搜尋端零改動。
- 驗收：evaluation 同大小 **≥18/270**；training 同大小 +5；每新規則 ≥1 單元測試；過 train 答錯 evaluation 不增（兩步規則須在全部 train 對、≥2 物件上一致才成立）。

## 3. 方向問題決定

1. **取捨**：如上；E3 不做；E6 併入線 A，但「產生器連同其產出積木」整包當子樹（可被上層產生器改良）屬 E3 範疇，列代定給 r06。
2. **引擎放 Python**：改寫在 Python 對同一 S 式 JSON 執行；janet 只當可讀表示與往返驗證。理由：熱路徑無子程序、pytest 好測、janet 缺席照常。不做「janet 寫規則表」混合版（兩邊 parse、除錯翻倍）。「janet 內執行」列代定，r06 若 E2 證明有效再評估。
3. **`$ref` 兩層都出、折疊只決定一次**：JSON 層 aos N-45 `{"$ref":"m_sub_x/program.json"}` 為正本（與帳本、memory 工具一致、子樹積木就是它）；janet 層 `defn` 是同一折疊的渲染，`from_janet` 讀到 `defn` 必須還原成 `$ref`。
4. **`_meta` 分數＝混合**（便宜分數篩、分紅決定保留），第 2 層調第 1 層的變異範圍；**本輪不實作**，由線 B ledger＋線 A 子樹積木進帳產出分紅樣本。列代定。
5. 驗收數字見 §4。
6. **預算**：每題 ≤8 s、≤3000 候選、種子 ≤5、編輯距離 ≤2。**防背答案**：(a) 只驗 train、絕不看 test；(b) 須過**全部** train 對；(c) 拒絕含 ≥3×3 字面格子或輸出尺寸字面常數；(d) 多候選先少編輯、再短程式；(e) 子樹積木須 ≥3 題 training 共用且無題專屬常數；(f) 改寫程式的「過 train 答錯」分開統計，超標收緊閘門。

## 4. 驗收數字（合併後全量各一次，`--workers ≤6`，開跑前 `pgrep -af "arcagi eval"`）

| 項 | r04 | 門檻 |
|---|---|---|
| evaluation | 37/400 | **≥42** |
| 同大小 | 13/270 | **≥18** |
| training | 92/400 | **≥100** |
| 過 train 答錯 eval／train | 13／24 | **≤13／≤24** |
| 退步 | 0 | 0（有則列原因） |
| 往返測試 | — | 365 積木＋training 解出程式 100% |
| 子樹積木 | 0 | ≥3 個 `m_sub_*`，≥1 個被改寫搜尋命中 |
| 全量 evaluation 時間 | — | ≤ r04 ×1.5 |

## 5. 風險與退路

- **改寫搜尋 0 增量**：`--rewrite` 預設關，保留程式與 ledger，03b 記每規則命中數與沒過 train 的原因；仍以線 A＋E4 交卷，evaluation 門檻降為 ≥40。
- **子樹挖不到 3 個**：門檻降 min_tasks=2 但不自動落成，只在 03a 列候選。
- **E4 推高過 train 答錯**：先拿掉形狀→色（最易背答案）。
- **線衝突**：C 禁碰 `solvers/`，B 只加一個呼叫點，A 只新增資料夾；合併順序 C→A→B。
- **janet 缺席**：`janet_bridge` 回 None、測試 skip，評測純 Python。
- **時間超標**：每題 8 s 硬上限，先砍候選再砍種子；全量前跑 ≤50 題子集量時。
- **代定清單**：E3 延後；引擎不放 janet；產生器整包當子樹留 r06；`_meta` 第 2 層調變異範圍。
