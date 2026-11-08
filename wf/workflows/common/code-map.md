# code-map — 程式碼導航

[common/README](README.md)｜[INDEX](../../INDEX.md)｜[conventions](conventions.md)

修改前先由相關入口追程式與測試；新增、刪除或調整職責後同步此頁。這裡是導航，行為以 code/tests 為準。

## 入口

<!-- wf-nav -->
- [tasks](../../../src/arcagi/tasks/__init__.py)：`Task`／`SolverTask`／`Grid`、官方 JSON schema 驗證與載入；[測試](../../../tests/tasks/)。
- [solvers](../../../src/arcagi/solvers/__init__.py)：`module:function` plugin、隱藏 test 答案、預測驗證；[identity](../../../src/arcagi/solvers/identity.py) 是流程基線；[測試](../../../tests/solvers/)。
- [runtime](../../../src/arcagi/solvers/runtime.py)：每題獨立程序執行與可選逾時；[測試](../../../tests/solvers/test_runtime.py)。
- [external](../../../src/arcagi/solvers/external.py)：跨語言 JSON request／response、可選 `{trace}` 軌跡檔、程序逾時與逐次 artifacts；sh／C 範例在 [examples](../../../examples/)；[測試](../../../tests/solvers/test_external.py)。
- [trace](../../../src/arcagi/solvers/trace.py)：`arcagi-trace/1` 驗證、`SolverResult`、`TraceRecorder`、`check_on_train`；[template](../../../src/arcagi/solvers/template.py) 是附軌跡的 plugin 骨架；[測試](../../../tests/solvers/test_trace.py)；格式文件 [traces](../../../docs/traces.md)。
- [dsl](../../../src/arcagi/dsl/__init__.py)：網格 DSL——[grid](../../../src/arcagi/dsl/grid.py) 純函式、[primitives](../../../src/arcagi/dsl/primitives.py)／[primitives_more](../../../src/arcagi/dsl/primitives_more.py) 原語與參數推斷、[registry](../../../src/arcagi/dsl/registry.py) 總表、[learners](../../../src/arcagi/dsl/learners.py) 終端換色表／鄰域規則、[program](../../../src/arcagi/dsl/program.py) JSON 程式執行與成本；[測試](../../../tests/dsl/)。
- 第二輪原語：[objects](../../../src/arcagi/dsl/objects.py)（物件選擇器＋動作；屬性在 [objects_props](../../../src/arcagi/dsl/objects_props.py)、終端學習器 [objects_learner](../../../src/arcagi/dsl/objects_learner.py)）、[cells](../../../src/arcagi/dsl/cells.py)（格線切塊）；registry 依 `aos/blocks/` 狀態過濾並載入巨集；[測試](../../../tests/dsl/)。
- 第三輪：[background](../../../src/arcagi/dsl/background.py)（題目層級背景 context，物件抽取用）、[features](../../../src/arcagi/dsl/features.py)＋[formula](../../../src/arcagi/dsl/formula.py)（公式型積木求值／擬合、`predict_shapes`）＋[formula_prims](../../../src/arcagi/dsl/formula_prims.py)、[extract](../../../src/arcagi/dsl/extract.py)（抽取型積木）＋[extract_prims](../../../src/arcagi/dsl/extract_prims.py)；產生器 [gen_formula](../../../src/arcagi/blocks/gen_formula.py)、[gen_extract](../../../src/arcagi/blocks/gen_extract.py)；投票 [vote](../../../src/arcagi/solvers/vote.py)；[測試](../../../tests/dsl/)。
- 第四輪：[objrule](../../../src/arcagi/objrule/__init__.py)（每物件規則：物件視角抽取 `view`、擬合 `fit`、原語 `recolor_from`／`move_from`／`extend_from` 在 `prims`、評分 `gen`）；帳拆成 [blocks/pool/](../../../src/arcagi/blocks/pool/__init__.py)（`ledger`、`budget.allocate` 決定產生器候選數）；[gen_meta](../../../src/arcagi/blocks/gen_meta.py)（產生器的產生器，調 gen_formula 設定）；`arcagi eval --workers N`；[測試](../../../tests/objrule/)。
- [blocks](../../../src/arcagi/blocks/__init__.py)：aos 接入——`aos/blocks/` 積木資料夾的 catalog／sync／run、node-pool 式記帳 pool、片段抽巨集 library、`aos/solver/_entry` 用的 solver；用法見 [aos/README](../../../aos/README.md)；[測試](../../../tests/blocks/)。
- [score_top2](../../../scripts/score_top2.py)：從 eval 報告的 `trace.metadata.second` 離線算 top-2。
- [search](../../../src/arcagi/solvers/search.py)：第一輪 DSL 枚舉求解器（`arcagi.solvers.search:solve`，觀察等價去重、最短程式勝出、軌跡記過 train 程式與近失敗）；[測試](../../../tests/solvers/test_search.py)；輪次紀錄 [r01](../../../notes/rounds/r01/03-設計.md)。
- [experiments](../../../src/arcagi/experiments/__init__.py)：設定驗證、task／method／seed／repeat 矩陣、JSON／CSV／HTML 報告；[測試](../../../tests/experiments/)。
- [eval](../../../src/arcagi/eval/__init__.py)：top-1 exact match、逐題報告（含耗時與軌跡）、外部 JSON 預測評分；[測試](../../../tests/eval/)。
- [compare](../../../src/arcagi/experiments/compare.py)、[labels](../../../src/arcagi/experiments/labels.py)：多份 eval／experiment 報告逐題對照、相對基線新增解出／退步、任意 task_id→category 對照檔分組；CLI 在 [cli_experiment](../../../src/arcagi/cli_experiment.py)；[測試](../../../tests/experiments/test_compare.py)。
- [CLI 參數](../../../src/arcagi/cli_args.py)與 [CLI I/O](../../../src/arcagi/cli_io.py)：argparse、題庫選取與 JSON 檔案邊界。
- [實驗報告](../../../src/arcagi/experiments/report.py)、[統計](../../../src/arcagi/experiments/statistics.py)、[HTML](../../../src/arcagi/experiments/report_html.py)：檔案輸出、分組分母、圖表呈現各自維護。
- [CLI](../../../src/arcagi/cli.py)、[進入點](../../../src/arcagi/__main__.py)：驗證、求解、評測（含 `--external`／`--traces`）、評分、比較、生成與瀏覽；[測試](../../../tests/test_cli.py)。
- [generation](../../../src/arcagi/generation/__init__.py)：固定 seed 的 RE-ARC adapter、生成驗證與 provenance；[測試](../../../tests/generation/)。
- [visualization](../../../src/arcagi/visualization.py)：純 stdlib 離線 HTML 題目瀏覽器；[測試](../../../tests/test_visualization.py)。
- [inventory_training](../../../scripts/inventory_training.py)：training 400 題特徵盤點，產生 `docs/inventory/` 的 HTML 與 CSV（繪圖在 [inventory_render](../../../scripts/inventory_render.py)）。
- [setup_data](../../../scripts/setup_data.py)：取得與核對固定來源；[CI](../../../.github/workflows/tests.yml)：lint、pytest 與官方題庫檢查。

## 真相層與維護鏈

`code/tests > schema/examples/fixtures > code map > docs > generated`。

衝突時以上層為準並修正下層。生成的 HTML 或報告不是唯一真相，來源與摘要衝突時以原始來源為準。修改程式後依序同步 code map 和人用文件，commit 前應一致；程式碼內不加反向指向 code map 的註解。
