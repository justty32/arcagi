# N4 題目特性採集 — 進度交接（第 1 棒 PARTIAL，23:4x 使用者喊停）

## 做到哪

- **規格寫完**：[gpuprofile-spec.md](gpuprofile-spec.md)（給 codex 的英文任務書，安全邊界已改為只寫 `native/gpu/profile/`）。設計要點：
  - 新程式 `native/bin/gpuprofile`，`#include "../kernel.cu"` 共用 N2 原語（同 gp 的做法），不改 N2 檔。
  - 每支程式在 train 上打分：`denom += max(輸出面積, 目標面積)`，重疊格算 `same` 與 11×10 的 `cnt[輸出色][目標色]`（跨所有 train pair 共用）；`raw = same/denom`，`cm = Σ_s max_g cnt[s][g] / denom`（套最佳單一一致 colormap 後），分數＝cm。gpusearch 的 exact／colormap 解必為 1.0。
  - kernel 結構照 `k_shared`（快取 pair-0 前綴狀態），但不提早淘汰；每 block 1024 格直方圖、`q >= thr_q` 的才寫進 hits；溢位時用該批直方圖提門檻重跑一次。
  - 主程式每深度保留前 M=64，CPU 用 train 輸出簽章去等價、留 K=8；輸出每深度 space/valid/fail/perfect/秒數/ge≥50..99/hist20/top-K。
- **CPU 特徵＋彙表工具完成**：`native/tools/profile_features.py`（純 stdlib）。已在無剖面下跑過：800 列、23 欄（尺寸、尺寸比、色數、新增／消失色、物件數、改動格比例、identity 分數、主線是否已解）。有 profile.jsonl 時再加 best_d1..d6、top1、prim_<17 原語> 頻率等欄；多檔合併取分數高／搜得深者。
- **Makefile 目標**：寫好但未 commit（原始碼還沒有，避免懸空目標）→ [makefile-gpuprofile.snippet](makefile-gpuprofile.snippet)，接手時原樣追加到 `native/Makefile` 末尾。
- **codex（arcagi-n4-codex）**：已讀完 N2 碼、尚未產出任何檔案即依停線指示停掉；`native/gpu/profile/` 目前不存在。

## 沒在跑的單元

無（arcagi-n4-codex 已 stop）。未開 GPU 批次。

## 下一步（關鍵路徑）

1. 追加 Makefile snippet；照 spec 重派 codex（`-m gpt-6.1-sol -s workspace-write -C native/gpu/profile`，spec 由 stdin 餵）或自己寫（kernel 約 150 行）。
2. **審 kernel**：分數不提早淘汰、`mapped==denom` 判 perfect、溢位重跑只用重跑那次的直方圖、decode 編碼同 gpusearch（`pidx*A+s`）。
3. 抽查：`gpuprofile --task data/ARC-AGI/data/training/3c9b0459.json --depth 2` top-1 應為 rot180、score 1.0；00d62c1b 同樣查 top-1。
4. 800 題：建議 `--depth 5 --dedup 3 --budget 20`，training／evaluation 兩程序並跑（各約 0.5 GB 顯存），包 `systemd-run --user --scope --unit=arcagi-n4-<名> -p MemoryMax=12G nice -n 19`。
5. `profile_features.py <jsonl…> --out reports/task-features-1109/features.csv --solved reports/native-cuda-1109/mainline-solved-*.txt`；欄位說明寫在本夾 README（data-files：md 留欄位說明與統計）。profile.jsonl >5 MB 不 commit，寫重生指令。
6. 新規則：今晚只本機 commit，不 push、不 pull。
