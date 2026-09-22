# organize — 把一堆資訊整理成好導航的結構

[WORKFLOWS](../WORKFLOWS.md)｜[INDEX](../INDEX.md)

散落的筆記、材料、檔案重新分類並給導航。這是 [STRUCTURE](../STRUCTURE.md) 結構整理原則的**日常應用（非程式版）**：原則在那邊，這裡是動手流程。

**何時用**：某檔大到難讀、某資料夾不同用途混在一起難找，或使用者說「幫我整理一下這堆」。
**何時不用**：只有兩三個檔、翻一下就找得到。要改的是**內容**而不是**位置** → [write](write.md)。整理的是原始碼結構 → 開發 flavor 的 refactor / conventions。

## Done when

- 每個新分出來的子資料夾頂層有 `README.md` 或 `INDEX.md`。
- 原本的頂層位置只剩指標與連結，沒有細節。
- [common/info-map](common/info-map.md) 表每列「負責什麼」非空。

## 流程

1. 按內容 / 用途 / 主題**語意分**，不是 1/2/3 硬切等分；拆出來的每塊要有單一清楚的職責。
2. 放進專屬子資料夾，或併進既有的主題檔。
3. 子資料夾頂層留 README / INDEX 做導航；已有就更新它。
4. 原位置只留精簡指標 + 指向導航的連結。
5. **只搬不改內容**，保留原意；一次只動一個面向（先分類、或先改寫，不混做）。
6. 過時 / 被取代的材料進 `archive/`，不刪（規則見 [STRUCTURE](../STRUCTURE.md)）。

## 導航 index

材料多到難定位時，維護一份導航 index：[common/info-map](common/info-map.md)（`材料 | 位置 | 負責什麼 | 衍生產物`）。它與開發 flavor 的 code map 刻意對稱——維護鏈是**材料 → info-map → 衍生產物**，改了源頭就同步 index。

## 交接

- 整理完要重寫某份內容 → [write](write.md)；整理出來的是學習筆記樹 → [learn](learn.md)。
- 要刪東西、或動到使用者的私人檔案 → 先問（守鐵律 2：授權來源）。
- 整理到一半停手 → [SESSION-LOG](../SESSION-LOG.md) 一行寫清楚搬到哪。
