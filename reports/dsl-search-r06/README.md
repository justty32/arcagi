# dsl-search-r06：混合入口＋合成集門檻元優化＋S2 候選入庫，evaluation 能否 >42

- 指令：`ARCAGI_FORCE=1 scripts/eval_r06.sh {training|evaluation} dsl-search-r06`（＝`systemd-run --user --scope -q -p MemoryMax=16G nice -n 19 uv run arcagi eval --split <s> --external 'native/bin/solve {input} {output} {trace}' --timeout 40 --workers 6`；`ARCAGI_FORCE=1` 是因 S3 同時在跑 216 題子集）；`make -C native` 於 S1 commit 45668f9 之後。commit：training head 541ddb6、evaluation head 4f4a646；**工作樹含 S3 families**（S3 事後原樣 commit 7220e25；`rays_key` 約 14:40 才註冊，training 最早幾題可能沒有它）。
- 結果：**evaluation 56/400**（同大小 **23/270**）、**training 138/400**（同大小 84/262），errors 0；每題最長 19.0 秒；逐題耗時合計 evaluation 5093 秒（r05 1974）、training 3491 秒。
- 基準：dsl-search-r05 evaluation 38、training 96；native-s1 42。退步：evaluation 0（對 r05 與 native-s1）；training 2（`239be575` 改寫預設關所致、`0b148d64` 線 A 新積木庫所致）。
- 結論：**是**，+18 evaluation、退步 0；但增量幾乎全來自支線原語，主線三線本身 evaluation 0 增量。

## 歸因（evaluation 新解 18 題，`scripts/attribution.py`）

| 來源 | 題數 | 題 |
|---|---|---|
| S1 新原語 `x_*`（C++ 搜到） | 7 | 1a2e2828、21f83797、45bbe264、7039b2d7、ce8d95cc、e1baa8a4、fc754716 |
| C++ 寬樹（S1 r1 已有的 4＋新 1） | 5 | 358ba94e、5ffb2104、d56f2372、f5aa3634、be03b35f |
| S3 families（`bridge`、`stamp_key`、`halo8_key`） | 5 | 070dd51e、aa18de87、c92b942c、f0df5ff0、aa4ec2a5（C++ 接 Python 前綴） |
| 主線 `n_holes`（S2 缺原語訊號） | 1 | 37d3e8b2 |

- 分數拆分：evaluation Python 自己 43、native 補 13；training Python 121、native 補 17。
- 用到產生積木的答對題：evaluation extract 5、formula 2、pred 1（多為帳上有收入、受合成集豁免的那幾顆）；training 另有 `llm_*` 2 題（自題自解）。
- 過 train 答錯：evaluation Python 17（r05 14）＋native 12；training Python 30（r05 26）＋native 27——**未達**「不增」與挑戰目標 ≤20。來源待 r07 拆（S3 `stamp_key` 大表、`x_vrule`、native 無投票）。

## 題型（S4 labels，`reports/dsl-search-r06/rates.csv`）

evaluation：overlay 10/19、crop 8/21、scale_tile 8/28、draw 7/73、recolor 6/55、move 4/30、pattern 3/46、reshape 3/36、summary 3/18、fill 2/24、objects 2/39、multi 0/10。

## 主線三線的數字

- 線 A（4030ca1）：合成集多數門檻接進三台產生器；live extract 50→14、formula 35→19、pred 60→60；雙折 meta 只採 1 個 extract 設定（關 pred_selectors，兩折淨勝 +4／+2），formula 全部否定結果；meta 帳 `aos/meta/ledger.jsonl` 35 筆。
- 線 B（e4a5867）：改寫預設關（r05 改寫解的 feca6190 改由他法解出，239be575 失去），耗時省去改寫的 ×3；`attribution.py`、`intercept.py`、`eval_r06.sh`。
- 線 C（ad45c8a）：影子工具；S2 候選 37 顆過 11、入庫後 6 顆單題巨集改 covered（D-r6-12）；預核現有 186 顆產生積木過 65。
- 帳 epoch 6（training 報告）：income 138000、守恆 ok，96 顆 covered 退休。

## 下一步

見 [r06 總結](../../notes/rounds/r06/04-總結簡報.md) §6：r07 主軸轉元優化（小題組學習曲線）。
