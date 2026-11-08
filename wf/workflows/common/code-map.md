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
