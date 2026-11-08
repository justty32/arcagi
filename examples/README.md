# 可執行範例

從 repo 根目錄執行：

```sh
uv run arcagi experiment examples/experiment.json --output artifacts/example-run
```

[experiment.json](experiment.json) 定義兩題、identity 與 zero 兩方法、兩個 seeds、兩次 repeats；成功完成為 16 runs、0 errors，0 分正常。[file_identity.py](file_identity.py) 示範外部程式如何讀 request、套用 params、寫 response。

非 Python 範例：[sh_identity.sh](sh_identity.sh)（POSIX sh）與 [c_identity/solver.c](c_identity/solver.c)（C99），都會額外寫一份[嘗試軌跡](../docs/traces.md)。[experiment-cross-language.json](experiment-cross-language.json) 同時跑 Python 與 sh 版本：

```sh
uv run arcagi experiment examples/experiment-cross-language.json --output artifacts/cross-language
uv run arcagi eval --split evaluation --name sh-identity \
  --external "sh examples/sh_identity.sh {input} {output} {trace}" --output artifacts/sh-identity.json
```

Python plugin 骨架（含軌跡回報）在 [src/arcagi/solvers/template.py](../src/arcagi/solvers/template.py)。

結果放在指定的新目錄，開 `report.html` 看圖表，讀 `results.json` 查看每次紀錄。重跑請換新的 output 目錄。設定內相對路徑以 `examples/` 為起點；新增語言或方法請看 [逐步教學](../docs/experiments/quickstart.md) 與 [檔案契約](../docs/experiments/protocol.md)。
