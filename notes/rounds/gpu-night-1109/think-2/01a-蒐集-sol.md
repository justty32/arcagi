蒐集方式：只讀本機文件、程式與資料；未跑測試、求解器或 GPU，未修改檔案；末次檢查未見 `~/arcagi-STOP`。

## Q1 活樹 hammer 的檔案結構

- **來源路徑**：`/home/lorkhan/code/playground-arc1/ws/hammer/_metainfo.json:6–18`；`/home/lorkhan/code/playground-arc1/ws/hammer/frozen.json:2–51`；`/home/lorkhan/repo/arcagi/src/arcagi/hammer/formats.py:330–347`  
  **摘錄**：
  ```python
          "layers_max": 3, "priors": [],
          "budgets": {**BUDGETS, **(budgets or {})},
          "llm_tax_evals": LLM_TAX_EVALS, "foundry_wait_sec": 0,
          "split_ab": "sha1(task_id+'r09AB')",
  ```
  **相關性一句**：根 `_metainfo.json` 是定義描述（`born,entry,kind,name,reads,status,weight,writes`），`frozen.json` 是限制／設定（另含 `schema,tree,h24_floor,taskset,holdout,purity,judge`），其中 `taskset` 記路徑、SHA1、P 鍵名，`holdout` 記 H8／H24 數量與 SHA。

- **來源路徑**：`/home/lorkhan/code/playground-arc1/ws/hammer/ops.jsonl:1`；`/home/lorkhan/repo/arcagi/src/arcagi/hammer/epoch.py:442–447`  
  **摘錄**：
  ```json
  {"blamed_by": null, "born": {"by": "agent-r09", "epoch": 0}, "by": "agent-r09", "env_hash": null, "evidence": {"new_solves": [], "shadow_epochs": 0, "witness_hits": 0}, "id": "gate_g1", "kind": "gate", "mdl_bits": null, "parent_route": null, "payload": {"params": {"k": 2.0, "lib_cap": 16, "loo_frac": 0.25, "loo_min_pairs": 3, "m": 3, "max_holes": 2, "mdl_div": 1.0, "retire_after": 2}}, "sig": null, "status": "live", "tried_env_hashes": [], "ttl": 3}
  ```
  **相關性一句**：`ops.jsonl` 混合算子定義與執行期狀態，實查 21 列／21 個唯一 id 對應 14 個子夾且無多餘子夾，缺子夾的 `gate_g1`、`route_ok_rt_sleep`、`route_ok_rt_vsplit`、`route_starve_rt_pool`、`route_starve_rt_sleep`、`route_saturate_rt_vsplit`、`route_saturate_rt_gatescan` 正好符合程式只替 comb／decomp 建投影的條件。

- **來源路徑**：`/home/lorkhan/code/playground-arc1/ws/hammer/ops/decomp_halves/_metainfo.json:6–20`；`/home/lorkhan/code/playground-arc1/ws/hammer/nodes/grow/_metainfo.json:6–17`；`/home/lorkhan/repo/arcagi/src/arcagi/hammer/formats.py:354–360`  
  **摘錄**：
  ```python
          write_metainfo(d, node_meta(name))
          for sub in ("inbox", "outbox"):
              (d / sub).mkdir(parents=True, exist_ok=True)
          if not (d / "_witness.jsonl").exists():
              write_text(d / "_witness.jsonl", "")
  ```
  **相關性一句**：14 個 `ops/<id>/` 實際都只有 `_metainfo.json`（`id,kind,status,by,born,evidence,payload` 投影），七種 `nodes/{solve,gate,grow,stall,route,judge,foundry}/` 都有定義 `_metainfo.json`、執行期 `_witness.jsonl` 與 inbox／outbox，入口是 Python `module:function` 字串。

- **來源路徑**：`/home/lorkhan/code/playground-arc1/ws/hammer/epochs/8/curve.csv:1`；`/home/lorkhan/repo/arcagi/src/arcagi/hammer/epoch.py:428–455`；`/home/lorkhan/code/playground-arc1/ws/hammer/ledger.jsonl:1`  
  **摘錄**：
  ```python
      fm.write_json(ed / "status.json", status)
      fm.write_json(root / "live" / "_status.json", {**status, "time": fm.now()})
      fm.append_jsonl(root / "live" / "events.jsonl",
  ```
  **相關性一句**：`epochs/0..8/` 與 `live/` 都是執行期產物，前者每輪有單列 `curve.csv`、逐題 `solutions.jsonl`、JSON 陣列 `blocks.json/shadow_blocks.json` 與物件 `status.json`，後者有 `_status.json,state.json,events.jsonl,daemon.pid,daemon.log`，根 `ledger.jsonl` 則逐行追加事件物件。

- **來源路徑**：`/home/lorkhan/repo/arcagi/src/arcagi/hammer/formats.py:350–353`；`/home/lorkhan/repo/arcagi/src/arcagi/hammer/foundry.py:139–146`；`/home/lorkhan/code/playground-arc1/ws/hammer/README.md:48–51`  
  **摘錄**：
  ```python
      write_json(root / "truth" / "train" / "taskset.json",
                 {"L16": ids["L16"], "P": ids["P"]})
      write_json(root / "truth" / "cal" / "ids.json",
                 {"H8": ids["H8"], "H24": ids["H24"]})
  ```
  **相關性一句**：`truth/` 是初始化釘住的題號分池資料而非網格答案，`foundry/` 是執行期請求 Markdown、`wax/<task>.jsonl` 軌跡與 `work/<task>/{lib.json,subs.jsonl,subs.out.jsonl}` 中間檔，請求中的步驟格式為 `{pair,step,tag,grid}`。

- **來源路徑**：`/home/lorkhan/code/playground-arc1/ws/hammer/ctl:1–4`；`/home/lorkhan/code/playground-arc1/ws/hammer/RUN:1`；`/home/lorkhan/code/playground-arc1/ws/hammer/_view.sh:1–4`；`/home/lorkhan/code/playground-arc1/ws/hammer/README.md:42–53`  
  **摘錄**：
  ```bash
  #!/usr/bin/env bash
  # Thin shell over arcagi.hammer.ctl; HAMMER_ROOT defaults to this directory.
  HAMMER_ROOT="${HAMMER_ROOT:-$(cd "$(dirname "$0")" && pwd)}"
  cd /home/lorkhan/repo/arcagi && exec uv run python -m arcagi.hammer.ctl --root "$HAMMER_ROOT" "$@"
  ```
  **相關性一句**：`ctl/_view.sh` 是工具葉子而 `RUN` 是含時間戳的存在旗標，`find -type l` 無結果、`stat -c '%a %n'` 顯示兩腳本 755／RUN 與資料例子 644，全樹 97 檔的 `file` 結果皆文字或空檔、未見二進位與 `.py` 葉子，非 JSON 葉子另有 CSV、README／請求 `.md`、daemon `.log/.pid`。

## Q2 hammer 如何讀寫、梯度與成本欄位

- **來源路徑**：`/home/lorkhan/repo/arcagi/src/arcagi/hammer/formats.py:53–91,100–116`  
  **摘錄**：
  ```python
  def write_json(path: Path, obj) -> None:
      write_text(path, json.dumps(obj, indent=1, sort_keys=True) + "\n")
  ```
  **相關性一句**：`load_ops→read_jsonl` 忽略空白列並逐列 `json.loads`，`write_ops→write_jsonl` 每列採排序 key、無縮排、末尾換行，JSON 採一格縮排與末尾換行，整檔寫入經同目錄暫存、flush／fsync／replace，`append_ops` 檢查重複 id 後仍重寫整檔。

- **來源路徑**：`/home/lorkhan/repo/arcagi/src/arcagi/hammer/formats.py:174–183,226–238`；`/home/lorkhan/repo/arcagi/src/arcagi/hammer/judge.py:30–66`；`/home/lorkhan/repo/arcagi/src/arcagi/hammer/epoch.py:309–311`  
  **摘錄**：
  ```python
              "ttl": TTL, "env_hash": None, "parent_route": parent_route,
              "by": by, "born": {"epoch": epoch, "by": by}, "blamed_by": None,
              "tried_env_hashes": []}
  ```
  **相關性一句**：hammer 的現成歸責欄位是 op 的 `blamed_by` 與 ablate 帳列的 `blamed`，另有 `mdl_bits/evidence`，在 `src/arcagi/hammer/` 搜尋未見 `_grad_log` 或 gradient 信箱欄位，不能把它與 blocks 的 `_gradients.jsonl` 混稱。

- **來源路徑**：`/home/lorkhan/code/playground-arc1/ws/hammer/epochs/8/curve.csv:1–2`；`/home/lorkhan/repo/arcagi/src/arcagi/hammer/epoch.py:410–426`；`/home/lorkhan/repo/arcagi/src/arcagi/grow/pool.py:100–110`  
  **摘錄**：
  ```python
          "stall": stall, "arm": arm, "evals_body": evals["body"],
          "evals_shadow": evals["shadow"], "evals_meta": 0, "evals_foundry": 0,
          "llm_calls": 0,
  ```
  **相關性一句**：曲線的成本／資源鍵有 `logcost_L,lib_size,lib_bits,evals_body,evals_shadow,evals_meta,evals_foundry,llm_calls,wall_s`，逐題另有 `nodes,nodes_to_first,seconds`，其中 `logcost_L` 使用解題節點數的 log2、未解記預算上限，pass-0 已解題最多再計兩 bits 加速。

- **來源路徑**：`/home/lorkhan/repo/arcagi/src/arcagi/hammer/epoch.py:278,448–453`；`/home/lorkhan/repo/arcagi/src/arcagi/hammer/foundry.py:367–376`；`/home/lorkhan/repo/arcagi/src/arcagi/hammer/formats.py:123–125`  
  **摘錄**：
  ```python
          "evals": {"body": 0, "shadow": 0, "meta": 0, "foundry": nodes,
                    "llm_tax": tax}})
  ```
  **相關性一句**：ledger 每列補 `time` 並追加排序 key 的 JSONL，epoch 帳可含 `after.{solved_L,solved_H24,logcost_L}`、`lib_bits` 與 `evals.{body,shadow,meta,foundry,llm_tax}`，foundry ingest 另外記 LLM 稅而曲線沒有獨立 `evals_llm_tax` 欄。

## Q3 arcagi 內其他 aos 樹與 pool

- **來源路徑**：`/home/lorkhan/repo/arcagi/aos/README.md:8–17`；`/home/lorkhan/repo/arcagi/src/arcagi/seed/library.py:25–32,52–70`；`/home/lorkhan/repo/arcagi/aos/seedlib/empty/blocks.json:1`  
  **摘錄**：
  ```text
  blocks/<name>/_entry           # sh：stdin {"grid":..,"params":[..]} → stdout 網格
  blocks/<name>/_gradients.jsonl # 梯度信（近失敗），每積木上限 50 行
  blocks/<macro>/program.json    # 巨集＝參數已定的 JSON 程式
  ```
  **相關性一句**：實際頂層另有 `llm,meta,pool,seedlib,solver,.stack`，blocks 的產生器在 `_gen/`、謂詞／公式／抽取用 `_rule.json`，seedlib 各實驗子夾的 `blocks.json` 則是積木陣列（空庫 `[]`，基本欄位 `name,body,sig,src_tasks,saving,uses`）。

- **來源路徑**：`/home/lorkhan/repo/arcagi/src/arcagi/blocks/catalog.py:89–105,125–155`  
  **摘錄**：
  ```python
      """Splice ``{"$ref": ...}`` steps of a program list (aos N-45 ``$ref``).

      Each directive step is replaced by the referenced program's steps, resolved
      recursively from the referenced file's folder; a ``$ref`` list concatenates
      its parts in order. Non-directive steps and non-list values pass unchanged.
  ```
  **相關性一句**：catalog 支援相對於被參照檔的 `$ref`、JSON Pointer、引用列表依序串接及循環拒絕，但這次 `rg '\$ref' aos -g '*.json'` 與 `find aos -type l` 均無結果，所以目前資料樹未見實際 `$ref`／symlink 葉子。

- **來源路徑**：`/home/lorkhan/repo/arcagi/aos/pool/config.json:2–9,25–28`；`/home/lorkhan/repo/arcagi/src/arcagi/blocks/pool/ledger.py:130–163,174–179`  
  **摘錄**：
  ```python
                  part = price * share * Fraction(count, total)
                  dividends[name] = dividends.get(name, Fraction(0)) + part
  ```
  **相關性一句**：`settle` 以每解一題 1000、頂層保留 0.2、餘額依選中程式靜態引用分配，再將巨集分紅 0.5 下傳成分／產物分紅 0.2 給產生器，支出為 `block_calls/1000×cost + gen_seconds×generator_rate` 並扣每輪房租 100。

- **來源路徑**：`/home/lorkhan/repo/arcagi/src/arcagi/blocks/pool/ledger.py:180–199,247–268`；`/home/lorkhan/repo/arcagi/src/arcagi/blocks/pool/budget.py:31–40,54–71`  
  **摘錄**：
  ```python
          blocks_out[name] = {"balance": round(balance, 6), "dividend": dividend}
          blocks_out[name] |= {"spend": spend, "rent": config["rent"]}
          blocks_out[name] |= {"refs": refs.get(name, 0), "zero_streak": streak}
  ```
  **相關性一句**：pool 寫 `wallets.json`、`epochs/<n>.json` 與 ledger 的 `epoch/block/retire` 三型列，另記 `income_total,generator_budget,conservation_ok,suggest_retire`，連續零分紅三輪才列建議且排除 essential，而「有 generator 且 covered」者會實際改 `status=retired`，比 README 的「只由人改」更具體。

- **來源路徑**：`/home/lorkhan/repo/arcagi/src/arcagi/blocks/pool/ledger.py:114–116,151–160,203–210`  
  **摘錄**：
  ```python
              letter = {"from": "pool", "task": task.get("task_id")}
              letter |= {k: attempt.get(k) for k in LETTER_KEYS}
              letter["score"] = attempt.get("data", {}).get("pixel_acc")
              letter["says"] = "near miss on an unsolved task"
  ```
  **相關性一句**：blocks 的梯度信由未解題 near-miss 按 `pixel_acc` 排序選取，附 epoch 後寫被引用積木的 `_gradients.jsonl` 並受 50 行上限約束，而 `settle` 的分紅計算未讀回這些信作乘數。

## Q4 aos 轉換工具的格式規則

- **來源路徑**：`/home/lorkhan/repo/simple_tools/aos/proto8/docs/CONCEPTS/01-設計理念/02-C-51.md:3`  
  **摘錄**：
  > - **C-51** 資料夾與 JSON 可以互通：資料夾＝object、名字＝key，一份 JSON 本身也是一個小檔案系統，inst 體系以外的格式也能這樣套；「但是我會覺得，建議不要濫用，因為雖然可以互通，但畢竟在細節上有差異」——所以互通只當工具與思考方式，**不進規範**。

  **相關性一句**：此段提供資料夾／JSON 的概念對應及「不進規範」界線，同一原文後半另說隱藏檔原則上略過，因此不能直接視為完整、無損的檔案系統序列化契約。

- **來源路徑**：`/home/lorkhan/repo/simple_tools/aos/proto8/cmd/aos-grow/README.md:18–29`  
  **摘錄**：
  ```text
  | `up --to file` | 內嵌單子 | 那格寫 `"NAME"`；旁邊多一份 `NAME.json`（就是那張單子） |
  | `up --to dir` | 內嵌單子，或 `"NAME"`＋`NAME.json` | 那格寫 `"NAME"`；`NAME/_entry`（同一張單子）；`NAME.json` 刪掉 |
  ```
  **相關性一句**：grow 操作的是 `設定檔#/指標` 的呼叫格，down 只在子夾剩 `_entry`／無其他引用時縮回，搬動會修 cwd、相對 `$ref` 與 `AOS_CD` 路徑，碰 `AOS_CF/AOS_CO` 則拒搬，並非任意樹的通用 JSON 往返器。

- **來源路徑**：`/home/lorkhan/repo/simple_tools/aos/proto8/impls/aos-json/docs/01-用法與寫回去-原子-只改變的那一塊.md:20–27,35–42`  
  **摘錄**：
  > **`--check`**：寫之前把整份檔（含被 `$ref` 的）用 check 驗一次改完的樣子，**比原本多出問題**才擋（`CheckFailed`，一個都不寫）；原本就有的問題不擋。

  **相關性一句**：`ref --move` 搬子值並修其相對引用，`check` 查指向、循環、合併、指示詞及 exec 形狀且否定結果退 10，寫回採保權限原子更新與局部原文替換，但文件明列不保擁有者／硬連結且無鎖。

- **來源路徑**：`/home/lorkhan/repo/simple_tools/aos/proto8/extras/langs/janet/README.md:23,32–47`  
  **摘錄**：
  ```text
  | `(dir "a" x "b" y)` | 資料夾，裡面 `a`、`b` |
  | struct／table／tuple／字串／數字（放在 dir 裡） | 那個檔寫成 JSON（中文不跳脫、短的擠一行） |
  | `(obj "k" v …)` | JSON 物件、key 照寫的順序；值 `nil`＝不寫那個 key，要 JSON 的 null 寫 `null` |
  ```
  **相關性一句**：編譯器讀普通 Janet 的 `program` 值，`ref/env/inst` 生成 JSON 指示詞／單子，`text/script/sh/copy` 分別保留文字、755 腳本或原檔權限，一般 struct 使用固定優先鍵再按字母排序。

- **來源路徑**：`/home/lorkhan/repo/simple_tools/aos/proto8/extras/langs/janet/README.md:32,35`；`/home/lorkhan/repo/simple_tools/aos/proto8/extras/langs/janet/examples/steps.janet:7–10`  
  **摘錄**：
  ```janet
  (def program
    (aos-seq
      (say "one")
      (aos-par (say "two a") (say "two b"))
  ```
  **相關性一句**：現成範例顯示程式是可組合的 Janet 值，而依 README 語法縮成最小樹可寫 `(def program (dir "_entry" (inst ["echo" "hi"])))`（此最小式為依文件組合，未執行編譯）。

## Q5 Janet 寫法慣例與本機執行檔

- **來源路徑**：`/home/lorkhan/repo/langs/janet-lab/cheatsheets/資料與-io.md:8–26`；`/home/lorkhan/repo/langs/janet-lab/modules/aos/fsx.janet:67–73`  
  **摘錄**：
  ```janet
  (def s (json/encode d))
  (json/decode s)          # key 是「字串」
  (json/decode s true)     # ★ key 轉 keyword（建議）
  ```
  **相關性一句**：lab 用 `spork/json` 做 JSON⇄Janet、推薦 decode 傳 `true` 後用 keyword 取值，實際 aos 模組寫檔採兩格縮排與末尾換行，已有 encode／decode 的資料往返慣例。

- **來源路徑**：`/home/lorkhan/repo/langs/janet-lab/reference/序列與集合c-字典與組合.md:71–80`；`/home/lorkhan/repo/langs/janet-lab/cheatsheets/地雷.md:61`  
  **摘錄**：
  ```janet
  (prewalk (fn [x] (if (number? x) (* x 10) x)) [1 [2 3] 4])   # => (10 (20 30) 40)   遞迴進去了
  (postwalk (fn [x] (if (number? x) (* x 10) x)) @[1 @[2]])    # => @[10 @[20]]       array 進、array 出
  ```
  **相關性一句**：`walk` 只處理外層、prewalk／postwalk 才遞迴且保留容器類型，另有 prewalk 走入自己替換結果而無限重入的記錄，提供 S 式子樹操作的現成材料。

- **來源路徑**：`/home/lorkhan/repo/langs/janet-lab/reference/spork/資料格式與驗證.md:19–24`；`/home/lorkhan/repo/simple_tools/aos/proto8/extras/langs/janet/README.md:15`  
  **摘錄**：
  > ⚠ **`nils` 給 true 時，`null` 的 key 會整個消失**：因為 Janet 的 table 不能存 `nil` 當 value

  **相關性一句**：JSON null 與 key 次序有資料往返差異，而本機 `command -v janet` 實得 `/home/lorkhan/.local/bin/janet`、`stat` 為 755，僅確認存在未啟動 Janet／核對版本。

## Q6 節點池定稿機制與實測教訓

- **來源路徑**：`/home/lorkhan/repo/simple_tools/aos/proto8/thinking/2026-11/08/node-pool/README.md:28–36`；`/home/lorkhan/repo/simple_tools/aos/proto8/thinking/2026-11/08/node-pool/03-設計.md:36–48,60–64`  
  **摘錄**：
  ```json
   "cost": {"ktoken": 1.0, "wall_s": 0.1},
   "price_per_task": null, "price_factor": 1.2, "keep": 0.2, "rent": 1.0,
   "zero_epochs": 3, "clone_cap": 2, "essential": [], "chain_max": 2}
  ```
  **相關性一句**：定稿錢公式起步為千 token＋秒／10、頂層預算為接受任務數×價錢＋scope 節點數×房租，每層先報銷自己及子樹實耗、剩餘利潤留 20%／80% 按直接靜態引用分紅，負利潤由自身報銷份承擔。

- **來源路徑**：`/home/lorkhan/repo/simple_tools/aos/proto8/thinking/2026-11/08/node-pool/03-設計.md:52–54,62,73,81`  
  **摘錄**：
  > 節點信箱 `<def>/_gradients.jsonl`：照 02 §2，`{t, epoch, from, case, say, score, handled}`；`handled` 初始 `null`。

  **相關性一句**：梯度 score 限 −1～1、平均值轉 0.5～1.5 倍分紅乘數且無信為 1，`improve` 省略時指 reviewer、審查鏈最多兩層，review_round 讀未 handled 信並在處方換上後標記處理。

- **來源路徑**：`/home/lorkhan/repo/simple_tools/aos/proto8/thinking/2026-11/08/node-pool/03-設計.md:63–77`  
  **摘錄**：
  > 輸出一律英文、錯誤經 `tool_io`。不叫 LLM。複製（specialize）照舊走 `agents new`，起始金由隊長在按 new 後跑一次 `pay` 的 `clone_seed`——第五輪不自動化（02 方向題 Q3 推薦 B）。

  **相關性一句**：扣款後餘額≤0 累積三輪只列建議、排除 essential／reviewer，正式退休需隊長操作後搬入 `defs.retired/<def>/<時間>/`，可 revive 並由 root 撥一任務價起始金，複製亦保留人工流程。

- **來源路徑**：`/home/lorkhan/repo/simple_tools/aos/proto8/thinking/2026-11/07/arknights-kb/28-帶去arcagi清單.md:48–52,58–60`  
  **摘錄**：
  ```text
  | 梯度信 | 上級對子定義的一行意見，寫進子定義的 `_gradients.jsonl`，分紅時換成 0.5～1.5 倍乘數 | [03 §2、§5](../../08/node-pool/03-設計.md)；`pool grad` | 對應「搜尋器對某積木的評語」（例：常被選中但最後答錯）；第五輪讀信那頭試過是好的，自動寄信那頭沒接上（[代定 99](代定清單.md)） | 半成品 |
  ```
  **相關性一句**：清單把帳／分紅／梯度／退休列為半成品，記有最貴節點先餓死、零花費腳本永不退、每 pass 都叫同批節點致退休訊號量不到、meta 七筆約 223 萬 token／2665 分尚未回本，以及空基準 tag 曾兩次夾入學得產物的教訓。

## Q7 思考輪 1 遺留與腳本介面

- **來源路徑**：`/home/lorkhan/repo/arcagi/notes/rounds/gpu-night-1109/think-1/02-規劃-fable.md:71–76`；`/home/lorkhan/repo/arcagi/notes/rounds/gpu-night-1109/think-1/03-設計.md:152–154`  
  **摘錄**：
  > - 同設定跑 2 次 → `meta/noise.json`：`sigma_auc_L`、`sigma_cost`。門檻：σ_auc_L ≤ 2 才可當尺；超過就要先找非決定性來源（threads、dict 順序）。

  **相關性一句**：塊 B 原提案是排除 epochs／live／tmp／ledger 後複製空起點樹、L=25000／P0=10000／4 epochs、目標≤40秒並另記 meta 帳，但正式設計仍寫「下一輪再細化」，不能當已完成資產。

- **來源路徑**：`/home/lorkhan/repo/arcagi/notes/rounds/gpu-night-1109/think-1/02b-Argon審.md:7–9`  
  **摘錄**：
  > 1. **【邏輯漏洞／塊 C & D2】拿 P 池（驗證池）題目造積木再送回影子快道，構成嚴重資料洩漏（Data Leakage）**

  **相關性一句**：審稿原文進一步要求候選生成 I0／D2 嚴格只看 L16，警告用 P 的 near_top 或 DStep 解定製 comb 會在同一 P 影子快道虛增 `new_solves`。

- **來源路徑**：`/home/lorkhan/repo/arcagi/notes/rounds/gpu-night-1109/think-1/02b-Argon審.md:22–24`  
  **摘錄**：
  > 4. **【概念與門檻錯誤／塊 C】用「格子相符率提升 $\ge 0.10$」抽填洞子樹當 comb，會製造大量刷色垃圾與非法懸空 AST**

  **相關性一句**：審稿以背景塗色可提高相符率 30%～80%及 lam 內 `$0` 抽出後未綁定兩項原因質疑該門檻，這是原稿警告而非本次新增設計結論。

- **來源路徑**：`/home/lorkhan/repo/arcagi/notes/rounds/gpu-night-1109/think-1/03-設計.md:50–66`；`/home/lorkhan/repo/arcagi/scripts/think1_audit.py:162–184`  
  **摘錄**：
  ```python
      parser.add_argument("tree_root", type=Path)
      parser.add_argument("--epoch", type=int)
  ```
  **相關性一句**：audit 預設最新完成 epoch、寫 `think1/audit/epoch-N.jsonl` 並印計數摘要，欄位為 `id,kind,status,by,mdl_bits,born_epoch,age,shadow_epochs,witness_hits,new_solves_n,uses_L,uses_P,hit_rate_10,idle_epochs,verdict,rules_version,note`，且卡片不讀 H8／H24。

- **來源路徑**：`/home/lorkhan/repo/arcagi/notes/rounds/gpu-night-1109/think-1/03-設計.md:92–116`；`/home/lorkhan/repo/arcagi/scripts/think1_meter.py:75–95,128–145`  
  **摘錄**：
  ```python
      parser.add_argument("tree_root", type=Path, nargs="?")
      parser.add_argument("--compare", type=Path, nargs=2, metavar=("A", "B"))
  ```
  **相關性一句**：meter 根目錄模式寫 `think1/meta/curve-summary.json`，輸出 `schema,tree_root,epochs,scored_epochs,auc_L,auc_P,auc_H24,auc_H8,logcost_L_base,logcost_L_final,auc_speed_L,cost,wall_s_total,llm_calls,eff,lib_size_final,lib_bits_final,stall_final,arm_final,per_epoch`，其中 AUC 排除 epoch 0、cost 包含全部完成 epoch 四類 evals。

- **來源路徑**：`/home/lorkhan/repo/arcagi/notes/rounds/gpu-night-1109/think-1/03-設計.md:118`；`/home/lorkhan/repo/arcagi/notes/rounds/gpu-night-1109/think-1/02b-Argon審.md:18–20`  
  **摘錄**：
  > **`--compare A B` 輸出**：`{"d_auc_L": B−A, "d_auc_speed_L": B−A, "d_cost": B−A, "d_eff": B−A, "sigma_auc_L": <float|null>, "significant": <bool|null>}`。

  **相關性一句**：compare 只讀、σ 取 A 同目錄 `noise.json`、缺檔則 significance=null，而 Argon 另警告小預算快撥可能使造詞失明及兩次決定論重跑不足以支撐原先的統計解讀。

## Q8 候選來源與相符率訊號的現況

- **來源路徑**：`/home/lorkhan/repo/arcagi/src/arcagi/grow/pool.py:1–10`；`/home/lorkhan/repo/arcagi/src/arcagi/hammer/epoch.py:245–252,316–326`  
  **摘錄**：
  ```text
  * P (practice) is searched every pass with an iterative-deepening budget and
    feeds G1, never AUC_L; H24 is measured only (D-r8-9).
  ```
  **相關性一句**：現行 `_main_run` 的 gate_ids 明列 L16∪P、`feed` 收所有 gate_ok 後交 `sleep_ops` 造候選，故 P 供造詞確有實作，但其程式定義是 practice、與 Q7 審稿稱 P 為驗證池有用語差異，H8／H24 不在這條 gate 來源中。

- **來源路徑**：`/home/lorkhan/repo/arcagi/src/arcagi/hammer/scan.py:13–21,120–142`；`/home/lorkhan/repo/arcagi/src/arcagi/grow/curve.py:257–259,308–325`  
  **摘錄**：
  ```python
      out = {"learn": learn, "P48": pl.subset(p48, seed, 0.75),
             "holdout": [], "holdout24": []}
  ```
  **相關性一句**：layer-2 scan 會從既有 solutions 重算 gate 並產生 comb 集、在 L16＋P48 子集試短曲線且清空 holdout，另一路 curve 的 cold-start near 語料與 G4 donors 明確限制 learn_ids，因此不能把所有 near／holdout 命中都當洩漏。

- **來源路徑**：`/home/lorkhan/repo/arcagi/src/arcagi/seed/enum.py:54–64,124–134`；`/home/lorkhan/repo/arcagi/src/arcagi/grow/evolve.py:1–3,22–31,119–121`  
  **摘錄**：
  ```python
              if typ == INPUT and not self.sub:
                  sc = sum(map(elem_score, vals, self.outs)) / len(self.outs)
                  item = (sc, -self.nodes, prog)
  ```
  **相關性一句**：seed near 排序直接使用逐格相等比例，但完成解另查 `vals==outs`，G4 改用輸入／目標差異格的 `change_score` 並只在 best_fit≥1 回傳程式，查得的是搜尋訊號而非「提升 0.10 即升級 comb」的已落地門檻。

- **來源路徑**：`/home/lorkhan/repo/arcagi/src/arcagi/solvers/search.py:90–99,274–280`；`/home/lorkhan/repo/arcagi/src/arcagi/blocks/pool/ledger.py:114–116,151–160`；`/home/lorkhan/repo/arcagi/scripts/taxonomy_failsample.py:35–40`  
  **摘錄**：
  ```python
              kind="near_miss",
              program=to_json(program),
              train_results=results,
              data={"pixel_acc": round(acc, 4)},
  ```
  **相關性一句**：`pixel_acc` 確實流入 near-miss trace、pool 梯度信排序與 score、taxonomy 失敗樣本排序，但搜尋正式解在此使用 `train==targets`，這幾個位置的用途需分別保留。

- **來源路徑**：`/home/lorkhan/repo/arcagi/src/arcagi/objrule/families/keyed.py:203–214`；`/home/lorkhan/repo/arcagi/notes/rounds/gpu-night-1109/think-1/02-規劃-fable.md:80–84`  
  **摘錄**：
  ```python
              if partial and all(
                  _consistent(s, o, t) for s, o, t in zip(states, outs, targets)
              ):
                  loose.append(params)
  ```
  **相關性一句**：`partial` 在 keyed 指一致性約束下的局部候選而非格子比例，明確的 `match_after−match_before≥0.10` 候選門檻目前找到於思考輪 1 規劃稿，這次 `src/`／`scripts/` 未搜到 `cell_acc,match_ratio,P16,pool_P` 字面命中。

## Q9 GPU 可接介面、批次單位與顯存

- **來源路徑**：`/home/lorkhan/repo/arcagi/native/gpu/space.hpp:1–5,21–32`；`/home/lorkhan/repo/arcagi/native/gpu/gpu.hpp:9–21`  
  **摘錄**：
  ```cpp
  struct DStep { uint8_t op, a, b, pad; };
  // Device-side task image: inputs (train then test) and train targets.
  struct DTask {
      int ntrain, nall;
  ```
  **相關性一句**：gpusearch API 輸入一題的尺寸／位移 `DTask`、uint8 網格 inputs／targets 及 DStep 字母表，`gpu_run(depth,start,count,sols,...)` 批次評估索引區間並回解數／解字 `idx | kind<<62`，上限 16 組輸入、每網格 900 格。

- **來源路徑**：`/home/lorkhan/repo/arcagi/native/gpu/gp/gp.hpp:7–22`；`/home/lorkhan/repo/arcagi/reports/gpu-gp-1109/report.md:11–15`  
  **摘錄**：
  ```cpp
      int pop=65536, island=256, lmax=10, linit=6, tourn=4, immigrants=8, migrate=20;
      float pcx=0.5f, pmut=0.9f, len_pen=0.002f;
  ```
  **相關性一句**：GP 個體是長 1～10 的字母表索引序列，`gp_load` 同樣載單題、`gp_eval` 回 fitness／hits／best_idx、`gp_genome` 取 genes、`gp_breed` 演化族群，所以可同時評多支程式，但標頭沒有接收 hammer 整棵樹／多套 ops 與 judge 迴圈的介面。

- **來源路徑**：`/home/lorkhan/repo/arcagi/reports/native-cuda-1109/prototype.md:11–17,31,68–77`；`/home/lorkhan/repo/arcagi/reports/gpu-gp-1109/report.md:25`  
  **摘錄**：
  > - 顯存：gpusearch 一個程序約 512 MiB。

  **相關性一句**：文件中的 CLI 以 `--tasks` 題單、`--data-dir` 題庫、`--depth/--mode/--out` 產出 JSONL，程式空間為每題 59～125 個具參數步驟的序列，GP 長跑 pop=524288 記約 0.5 GB 顯存，以上均為既有量測紀錄而非本次 GPU 查詢。

- **來源路徑**：`/home/lorkhan/repo/arcagi/reports/gpu-gp-1109/report.md:12–14`；`/home/lorkhan/repo/arcagi/reports/gpu-gp-1109/progress.md:7,31–34`；`/home/lorkhan/repo/arcagi/reports/native-cuda-1109/prototype.md:43,52`  
  **摘錄**：
  > - 早期觀察：pass-1 前 33 題 C++ 判 4 題「解」（1fad071e、2013d3e2、239be575、25d8a9c8），Python 驗 **train 全過但 test 全錯**＝過擬合；化簡後仍長 3～8 步。GP 的「solved」只代表 train 一致。

  **相關性一句**：文件區分 GP 的逐格／colormap／形狀加權 fitness、train exact／終端 colormap 判解及 Python test 重驗，並明說 GPU 走格子步驟空間而 seed 的 AST forbid 尚未接入，現有解報告亦不直接寫入 `aos/blocks/`。

## Q10 本機文獻筆記

- **來源路徑**：`/home/lorkhan/repo/paper_readings/summarize/2501.17168_EvoGP.摘要.md:22–23`  
  **摘錄**：
  > - **張量化遺傳操作**：發現多數算子（單點交叉、子樹變異、hoist 變異…）共用同一基元——**子樹交換（subtree exchange）**。

  **相關性一句**：EvoGP 以 `node_type/node_value/subtree_size` 定長張量與子樹交換支援整個程式樹族群的 GPU 遺傳搜尋。

- **來源路徑**：`/home/lorkhan/repo/paper_readings/summarize/2501.17848_eggp_Equality_Graphs.摘要.md:19–24`  
  **摘錄**：
  > 2. **e-graph 交叉**：選定第一父代的交叉點後，把第二父代可選的子樹**限制在「替換後會生成未訪問表達式」的子集**；若該集為空或不交叉則回傳原父代。

  **相關性一句**：eggp 用 DAG／e-graph 的既存子結構 id 共用與等價飽和記搜尋史，讓交叉／變異避開已訪表達式，並另有 fitness／size 的 Pareto 版本。

- **來源路徑**：`/home/lorkhan/repo/paper_readings/summarize/2211.16605_Stitch.摘要.md:19–24`  
  **摘錄**：
  > - **效用函數＝壓縮**：U(A) = −cost(A) + cost（語料） − cost（重寫後語料），可分解為每個重寫位置的局部效用（抽象體大小 − 應用開銷 ＋ 多次使用同一參數的 multiuse 紅利），**不需實際執行重寫即可計算**。

  **相關性一句**：Stitch 由單洞自頂向下長抽象，利用匹配位置超集的壓縮上界剪枝，直接對跨題程式語料學可重用積木。

- **來源路徑**：`/home/lorkhan/repo/paper_readings/summarize/2006.08381_DreamCoder.摘要/01_一句話概括.md:13–17`  
  **摘錄**：
  > - **兩重自舉**：每次 sleep 的新庫承接前期概念（庫越長越深）；同時生成模型與識別模型互相自舉（更專門的庫給出更豐富的夢、更準的識別模型解更多任務再回饋下一版庫）。

  **相關性一句**：DreamCoder 的 wake／sleep-abstraction／sleep-dreaming 共同成長顯式 DSL 庫與搜尋模型，MDL 同時計入庫本身及重構後程式成本。

- **來源路徑**：`/home/lorkhan/repo/paper_readings/summarize/2412.03624_SemanticBackprop.摘要.md:19–23`  
  **摘錄**：
  > - **成本設計**：前向用便宜的 gpt-4o-mini、反向與參數更新用較貴的 gpt-4-turbo（前向呼叫次數遠多於反向）。

  **相關性一句**：Semantic Backprop 沿圖逆拓撲分配語意梯度、納入共享後繼的 sibling 資訊並聚合回饋，提供分層 credit assignment 與前向／改進成本分帳的筆記來源。

- **來源路徑**：`/home/lorkhan/repo/paper_readings/summarize/2512.07961_Brush_Clinical_SR.摘要.md:21–25`  
  **摘錄**：
  > - GP 框架：**ε-lexicase 選擇 + NSGA-II 存活**，多目標（MSE + 線性複雜度）；後處理用**不精確簡化**（[[2512.01682]] 的 LSH 法）壓縮。

  **相關性一句**：Brush 將條件／真／假三分支納入程式樹，並以誤差與複雜度多目標保留候選，提供成本不必壓成單一分數的既有文獻案例。

## 沒找到的

- **Q2**：hammer 原始碼內未找到 `_grad_log`／gradient 信箱機制；找到的是 `blamed_by/blamed`，梯度 JSONL 實作位於另一套 blocks／pool。
- **Q3**：目前 `aos/` 的 JSON 葉子未找到實際 `$ref` 用例，`find aos -type l` 未找到 symlink；解析能力存在於 catalog。
- **Q4**：指定 C-51 是概念文字，未在所讀工具入口找到涵蓋 JSONL、CSV、權限、symlink、二進位與執行期狀態的通用無損樹⇄JSON 契約；最小 Janet 式未實跑。
- **Q7**：塊 B 的完成產物未獲確認，正式設計仍標下一輪細化；未將規劃稿的快撥設定／雜訊公式當成定稿。
- **Q8**：`src/`／`scripts/` 無 `cell_acc,match_ratio,P16,pool_P` 字面命中；未找到規劃稿「相符率提升≥0.10 即抽成 comb」的已落地實作，也未找到 H8／H24 經上述 gate feed 造詞的路徑。
- **Q9**：限定只讀文件與標頭後，未取得 gpusearch／gpgp CLI JSONL 每列的完整欄位 schema，亦未見直接批次評估完整 hammer 樹變體的 API；顯存數字僅引用既有報告。