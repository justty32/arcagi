# dev-env — 開發環境、指令、外部工具

[WORKFLOWS](../WORKFLOWS.md)｜[INDEX](../INDEX.md)

這台機器上要能開發需要什麼、怎麼裝、跑什麼指令；外部工具設定與 env var 也收在這裡。

**何時用**：fresh clone、換機器、裝不起來、忘了指令、要加一個外部工具或環境變數。
**何時不用**：驗證 / 測試怎麼跑 → [testing](testing.md)；程式碼慣例 → [common/conventions](common/conventions.md)。

## Done when

- 照「流程（fresh clone 後）」走完，`uv run pytest -q` 回傳 0。
- 下面三張表沒有空欄；要使用者親自做的（帳號、授權、金鑰）在 [WAIT_USER](../WAIT_USER.md) 各佔一行。

## 流程（fresh clone 後）

1. `git submodule update --init`（拉 `data/ARC-AGI/` 資料集）
2. `uv sync`（建 `.venv` 並照 `uv.lock` 裝依賴）
3. 目前沒有 env var 要設；有的話填下方「外部工具與 env var」表
4. `uv run pytest -q` 確認裝好了

## 指令表

| 做什麼 | 指令 | 備註 |
|--------|------|------|
| 安裝依賴 | `uv sync` | `pyproject.toml` / `uv.lock` 變動後重跑 |
| build | 無 | 純 Python 套件，不需 build |
| 解一題 | `uv run python -m arcagi solve <task.json>` | 進入點 `src/arcagi/__main__.py`（規劃中）|
| 評測集跑分 | `uv run python -m arcagi eval --split training\|evaluation` | 分數數字是求解器改動的 Done when |
| lint / format | `uv run ruff check . && uv run ruff format .` | |

驗證與測試指令不列這裡——連同「誰跑」一起在 [testing](testing.md)。

## 外部工具與 env var

| 名稱 | 用途 | 怎麼取得 / 設定 |
|------|------|----------------|
| `uv` | Python 版本、虛擬環境與依賴管理 | `curl -LsSf https://astral.sh/uv/install.sh \| sh`；Python 版本由 `pyproject.toml` 的 `requires-python` 決定（規劃 ≥ 3.12），`uv sync` 會自動抓 |
| `git`（submodule）| 拉 ARC-AGI-1 資料集 | 系統套件即可 |
| env var | 目前沒有 | 出現時在此加列；金鑰不進 repo |

需要帳號、付費、授權才能取得的：守鐵律 2（授權來源），並在 [WAIT_USER](../WAIT_USER.md) 記一行。

## 交接

- 環境就緒要開工 → [feature-dev](feature-dev/README.md)；先確認驗證跑得動 → [testing](testing.md)。
- 同一個裝機坑第二次撞到 → [common/gotchas](common/gotchas.md)。
