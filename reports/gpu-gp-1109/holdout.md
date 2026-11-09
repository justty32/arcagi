# gpgp-ho：留一 holdout＋MDL＋最短化簡能不能壓下 GP 過擬合（N3d，11-10）

**一句話：不能。MDL（以 bit 計的長度懲罰）把假 solved 從 7/8 降到 3/4、程式中位長度 5.5→3，而且保住唯一真解；留一 holdout 反而更糟（真解 a79310a0 丟了，假 solved 4/4）——ARC 這類題 train 只有 2～4 組、輸出常是極小格，留一組太容易「碰巧也對」。**

## 做了什麼

- `native/bin/gpgp-ho`（`make -C native gpugp-ho`，原始碼 `native/gpu/gp/` 旗標式改動，預設行為與 gpgp 相同；`native/bin/gpgp*` 未重建）：
  - `--holdout loo`：最後一組 train 不進 GPU 適應度與判解；GPU 命中後由 host 用全部 train 重驗，留出組錯就拒（記 `host_rejects`）繼續演化。
  - `--mdl λ`：長度懲罰改為 λ·log2(字母數)／步（bit 計）；本輪 λ=0.003 ≈ 0.018～0.021／步，原版 0.002／步。
  - `--simplify min`：解出後枚舉所有子序列，取仍擬合全部 train 的最短者（原版是貪婪逐步刪）。
- 兩個設定：**mdl**＝`--mdl 0.003 --simplify min`；**ho**＝再加 `--holdout loo`。種子 1、每題 20 秒。
- 題組：real-40（pop 65536，同 `bench/real/gp.jsonl`）；on40＝整夜 `arcagi-n3-gp` pass-1 已 solved 的 8 題＋33 題隨機未解（seed 1109，pop 524288，同整夜），原版數字直接取整夜紀錄。test 對錯一律用 `native/tools/gpu_verify.py`（Python 重驗）。
- 冒煙：3c9b0459 原旗標與 ho 旗標都解出 `rot180`、test 對。

## 對照表

| 題組 | 版本 | 跑完題數 | train solved | Python test 對 | 假 solved（train 對 test 錯） | 假 solved 比例 | solved 程式長度（中位／各題） | solve 中位秒 | 總秒 | host 拒（holdout 擋下） |
|---|---|---|---|---|---|---|---|---|---|---|
| real-40 | orig | 40 | 1 | 0 | 1 | 100% | 7 ／ 1fad:7 | 3.64 | 784 | — |
| real-40 | mdl | 40 | 0 | 0 | 0 | — | — | — | 801 | — |
| real-40 | ho | 40 | 1 | 0 | 1 | 100% | 7 ／ 1fad:7 | 6.58 | 787 | 0 |
| on40 | orig | 41 | 8 | 1 | 7 | 88% | 5.5 ／ 1fad:7,2013:4,239b:8,25d8:2,a793:4,aabf:0,d9fa:7,f8ff:8 | 3.38 | 702 | — |
| on40 | mdl | 41 | 4 | 1 | 3 | 75% | 3.0 ／ 2013:4,25d8:2,a793:4,aabf:0 | 0.755 | 752 | — |
| on40 | ho | 41 | 4 | 0 | 4 | 100% | 3.0 ／ 2013:4,25d8:2,aabf:0,d9fa:8 | 0.538 | 757 | 7770 |

- ho 的 host 拒：f8ff0b80 7723 次（holdout 擋下大量假解，到時間仍沒解）、2013d3e2 46 次（最後仍給假解）、a79310a0 1 次（擋到後 20 秒內沒再找到，真解丟了）。
- 1fad071e：ho 照樣解出 8 步程式、test 錯，host_rejects=0。這題輸出是 1×5 計數條，3 組 train 中留出那組的輸出跟另一組完全相同，在 2 組上演化出來的程式自然「也對」。

## 白話

GP 會過擬合，是因為它用很多步硬湊出剛好吻合 2～3 組例子的程式。把長度罰重一點（MDL），它就比較不會湊長鏈：假解少一半、程式變短，真解還在。但「留一組考試」在 ARC 幫不上忙：例子本來就少，留出的那組常跟別組長得一樣（或答案只有幾種可能），湊出來的程式照樣會「碰巧答對」；反過來，真正的解在只看 2 組時反而更難被選中，所以丟了。整體 test 對的題數沒變好（原版 1、mdl 1、ho 0），樣本也小（單種子、9 個 solved），只能說 MDL 方向對、holdout 單用沒用。

## 下一步

1. 預設改用 `--mdl`（λ 再掃 0.003／0.006／0.01），不要 `--holdout loo`。
2. holdout 改成輪流留出每一組（k-fold，全部組都要被預測對才算），並跳過「留出組輸出與某組 train 輸出相同」或輸出 ≤5 格的題（低熵，不提供泛化資訊）。
3. 判解時加門檻：化簡後長度 ≤ 窮舉已證無解深度＋1，超過就當 train-only，不報 solved。
4. 多種子（≥3）重量，9 個 solved 的樣本太小，任何一題翻轉比例就差 10% 以上。

## 指令

```
make -C native gpugp-ho
reports/gpu-gp-1109/ho/run.sh ho     # 或 mdl；輸出 ho/{real,on40}-<cfg>.jsonl ＋ -verify.jsonl
python3 reports/gpu-gp-1109/ho/summarize.py -v
```

## N3e MDL λ sweep 結論（主 session 05:46，依 `ho/sweep-summary.md`）

λ∈{0, .003, .006, .01} × seeds 1–3，`--simplify min`、無 holdout、每題 20 s；real-40 的 λ=.01 只完成 2/3 seed（05:45 截止 TERM）。

- **on40**：λ 越大，train solved 越少（6.3→3.5），程式越短（中位 4.5→2.5），但 test 對始終只有 a79310a0 一題（0.5–1），**假 solved 比例不降**（82–88%）。
- **real-40**：λ=0 只解 1fad071e（test 錯）；λ>0 幾乎全空。假解 100%。
- **判讀**：MDL 懲罰只是把程式變短、少解幾題，並沒有把假解篩掉——GP 在真題上湊的是 train 的巧合，不是長度造成的過擬合。和 N3d「MDL 假解減半」相比，加大 λ 沒有額外收益；λ=0.003 與 0 幾乎無差。
- **建議**：GP 線不再調 λ；若要續，該加的是 N4g 提的「寫死顏色」「不冗餘」門或 holdout 以外的驗證，而不是長度懲罰。GP 結果不接進補位（N4g 已證只增假解）。
