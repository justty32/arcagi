S4 類別表 v1.1：13 個主類、每類 3～8 個子類；子類 id 寫成 `主類.子類`。標類時每題一個主類＋一個子類，判準「決定輸出的關鍵一步」。

← [taxonomy](README.md)

## 判定順序（衝突時由上往下取第一個成立的）

1. 整張圖只做幾何變換 → `geometry`。
2. 輸出尺寸是輸入的整數倍、內容由輸入複製／放大而來 → `scale_tile`。
3. 輸出是輸入裡某一塊（原樣或幾乎原樣）→ `crop`。
4. 輸入被分隔線或尺寸切成幾塊、輸出是各塊疊合／比較 → `overlay`。
5. 輸出編碼的是「數量／屬性／判斷」而不是空間內容 → `summary`（v1.1：同尺寸也算，例 6e02f1e3、5582e5ca）。
6. 其餘尺寸改變 → `reshape`。
7. 同尺寸：依關鍵動作歸 `recolor`／`fill`／`pattern`／`draw`／`move`／`objects`；多個規則各占一半、說不出主步 → `multi`。

## 類別

已抽到 [categories.csv](categories.csv)（63 列）。欄位：`category` 主類、`subcategory` 子類 id（`主類.子類`）、`definition` 定義、`examples` 例題（training，空白分隔）。

13 主類：geometry、scale_tile、crop、overlay、summary、reshape、recolor、fill、pattern、draw、move、objects、multi；每類 3～8 子類。

## 版本

- v1（2026-11-08）：首版；第一版 inventory 的 14 粗類對到本表：fill→fill／draw／pattern、same_mixed→多類、shrink_other→reshape、split_overlay→overlay。
- v1.1（2026-11-08）：依 16 批標類回報的缺口（`move.sort` 2 題、其餘各 4～11 題）加 7 子類：`scale_tile.tile_plus`、`fill.color_by_region`、`fill.leak_ray`、`pattern.repair_patch`、`move.fit_into_hole`、`move.sort`、`objects.stamp_transformed`；summary 不限小圖。44 題改標記在 [overrides.csv](overrides.csv)，合併時覆蓋子 agent 的標籤。
- 標類時遇到放不進的題，記 `multi.other` 並在 rule 欄寫一句，累積 ≥10 題再開新子類（表才穩定）。
