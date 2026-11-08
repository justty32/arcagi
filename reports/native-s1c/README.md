支線 S1 第三任：native 改成「小題組快評測引擎」（arcbatch），並在 native 這段加支持度守門，收「過 train 卻答錯」。

← 第二任 [05 第二輪](../native-s1/05-第二輪.md)｜第一任 [04 總結](../native-s1/04-總結.md)｜交棒 [交棒.md](交棒.md)

## 結論

- **arcbatch**（`native/bin/arcbatch`＝`arcsearch --batch`）：一個行程跑「題 × 設定」，C++ 執行緒並行，不經 Python。20 題小集（training，seed 7）節點預算 25k：**7 題、CPU 2.4 秒（6 執行緒估牆鐘 0.4 秒）**；同一批題 r06 混合入口要 146.6 秒（逐題加總），其中光 Python search 那段就 34.4 秒，解 9 題（Python 7、native 補 2）。第二次跑同設定讀快取，0.0003 秒。
- **單執行緒速度**：物件抽取的快取鍵改成一格一個位元組、編譯改 `-O3 -march=native -ffp-contract=off`，同一題 40 萬節點從 3.83 秒降到 2.22 秒（1.7 倍）。程式與節點數跟舊 binary 完全一致（抽 3 題比對 solutions、nodes；1 與 6 執行緒輸出逐行一致；`tests/native` 全綠）。
- **支持度守門**（只用 training 定）：以 `local_rule`／`x_vrule` 結尾的程式，要求「train 輸出總格數 ÷ 表的列數」≥ 4（整個程式就是這張表）或 ≥ 16（表前面還有別的步驟）。在 r06 native 會答題的 training 題上：**答錯 26 → 9，答對 18 → 18**。

<!-- wf-nav -->
以下章節按語意拆到同資料夾的子檔，原文照搬：
- [arcbatch 用法](arcbatch用法.md)
- [數字；支持度守門怎麼定的；改了什麼；代定](數字守門與改動.md)
