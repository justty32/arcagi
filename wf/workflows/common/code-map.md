# code-map — 程式碼導航

[common/README](README.md)｜[INDEX](../../INDEX.md)｜[conventions](conventions.md)

修改前先由相關入口追程式與測試；新增、刪除或調整職責後同步此頁。這裡是導航，行為以 code/tests 為準。

## 入口

<!-- wf-nav -->
- [tasks](../../../src/arcagi/tasks/__init__.py)：`Task`／`SolverTask`／`Grid`、官方 JSON schema 驗證與載入；[測試](../../../tests/tasks/)。
- [solvers](../../../src/arcagi/solvers/__init__.py)：`module:function` plugin、隱藏 test 答案、預測驗證；[identity](../../../src/arcagi/solvers/identity.py) 是流程基線；[測試](../../../tests/solvers/)。
- [runtime](../../../src/arcagi/solvers/runtime.py)：每題獨立程序執行與可選逾時；[測試](../../../tests/solvers/test_runtime.py)。
- [external](../../../src/arcagi/solvers/external.py)：跨語言 JSON request／response、程序逾時與逐次 artifacts；[測試](../../../tests/solvers/test_external.py)。
- [experiments](../../../src/arcagi/experiments/__init__.py)：設定驗證、task／method／seed／repeat 矩陣、JSON／CSV／HTML 報告；[測試](../../../tests/experiments/)。
- [eval](../../../src/arcagi/eval/__init__.py)：top-1 exact match、逐題報告、外部 JSON 預測評分；[測試](../../../tests/eval/)。
- [CLI](../../../src/arcagi/cli.py)、[進入點](../../../src/arcagi/__main__.py)：驗證、求解、評測、評分、生成與瀏覽；[測試](../../../tests/test_cli.py)。
- [generation](../../../src/arcagi/generation/__init__.py)：固定 seed 的 RE-ARC adapter、生成驗證與 provenance；[測試](../../../tests/generation/)。
- [visualization](../../../src/arcagi/visualization.py)：純 stdlib 離線 HTML 題目瀏覽器；[測試](../../../tests/test_visualization.py)。
- [setup_data](../../../scripts/setup_data.py)：取得與核對固定來源；[CI](../../../.github/workflows/tests.yml)：lint、pytest 與官方題庫檢查。

## 真相層與維護鏈

`code/tests > schema/examples/fixtures > code map > docs > generated`。

衝突時以上層為準並修正下層。生成的 HTML 或報告不是唯一真相，來源與摘要衝突時以原始來源為準。修改程式後依序同步 code map 和人用文件，commit 前應一致；程式碼內不加反向指向 code map 的註解。
