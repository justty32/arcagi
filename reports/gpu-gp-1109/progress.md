# N3 GPU 遺傳式程式搜尋——交棒進度（11-09 23:03，PARTIAL，因 30% context 規則換手）

## 做到哪
1. 已讀規矩、N2 報告與 `native/gpu/`（kernel.cu／driver.cpp／space.hpp／gpu.hpp）。
2. **設計定稿＝施工任務書**：`/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n3/task.md`（接手者先讀這份，它就是設計）。要點：
   - `gp_kernel.cu` 直接 `#include "../kernel.cu"`，原語與 `Verdict` 判解與 N2 完全同一份；
   - 族群＝字母表索引序列（長度 1..10），65536 個體、256 島；適應度 = 0.5·逐格相符 + 0.35·列聯表 colormap 相符 + 0.15·形狀 − 0.002·長度；train 全過 `Verdict` 且 test 合法才算解，CPU 再以 arcsearch 原語確認並貪婪化簡（`depth`＝化簡後步數）；
   - 菁英、環狀遷移、隨機移民、錦標賽、一點交配、四種突變；`--random` 為無選擇對照組；
   - `--synth` 模式造「植入深度 L、且深度 < min-depth 全空間無解」的合成題。
3. `native/Makefile` 已追加 `gpugp` 目標（物件放 `native/bin/gp-obj/`，不碰 N2 的 `gpusearch-overnight`）。
4. **codex（gpt-6.1-sol）正在施工** `native/gpu/gp/{gp.hpp,gp_kernel.cu,gp_main.cpp}`：systemd 單元 `arcagi-n3-codex`，日誌 `.../scratchpad/n3/codex.log`，回報 `-o .../scratchpad/n3/codex-report.md`。23:03 時 gp.hpp、gp_kernel.cu 已寫，gp_main.cpp 進行中。
5. 隊長已寫好（未經實跑）：
   - `native/gpu/gp/bench.sh LIST OUT B [VERIFY_DATA]`：同題組、同每題秒數依序跑 GP、random、gpusearch（dedup 4、深度 ≤8、stop-first），再各自交 `native/tools/gpu_verify.py` 驗 train／test。
   - `native/gpu/gp/overnight.sh`：主線未解題多輪（預算 20→60→120→240 秒、seed 遞增、只重跑未解），結束或被 TERM 都呼叫 `overnight_summary.py` 寫 `reports/gpu-gp-1109/overnight-summary.md`。預設二進位 `native/bin/gpgp-overnight`（啟動前 `cp native/bin/gpgp native/bin/gpgp-overnight`）。
   - `native/gpu/gp/overnight_summary.py`：彙總＋Python 重驗＋與 N2 `reports/native-cuda-1109/overnight/phase-*.jsonl` 交叉。
   - 題單：`reports/gpu-gp-1109/real-40.txt`／`real-40-paths.txt`（主線未解，training、evaluation 各 20，seed 1109）、`synth-sources.txt`（40 個 training 來源題）。

## 下一步（接手者）
1. 等 `arcagi-n3-codex` 結束（`systemctl --user is-active arcagi-n3-codex.scope`），讀 codex-report.md，審 diff（只該新增 gp.hpp／gp_kernel.cu／gp_main.cpp；N2 檔不得改：`git status native/gpu`），`make -C native gpugp`，跑 smoke：3c9b0459 應 `solved:true`。沒做完就 `codex exec resume --last "<收尾提示>"`（沙箱可能不能用 GPU，實跑由隊長做）。
2. 量每代時間（stderr 每 200 代一行），必要時調 `--pop`。
3. 合成題：`native/bin/gpgp --synth reports/gpu-gp-1109/synth/L{5,6,7} --tasks reports/gpu-gp-1109/synth-sources.txt --synth-len L --min-depth 4 --seed L`，各取一份題單（`ls .../L*/*.json`）。
4. 比較（每條包 `systemd-run --user --scope --unit=arcagi-n3-bench-<名> -p MemoryMax=16G nice -n 19`）：`native/gpu/gp/bench.sh reports/gpu-gp-1109/real-40-paths.txt reports/gpu-gp-1109/bench/real 20`；合成題 `bench.sh <list> reports/gpu-gp-1109/bench/synth-L6 20 reports/gpu-gp-1109/synth/L6`。注意 N2 長跑同時佔 GPU，三組依序跑、同受干擾。
5. 寫 `report.md`（設計、數字表：解題數、解到的深度、Python train／test 件數、指令、commit）與 `notes/rounds/gpu-night-1109/gp-白話.md`；commit（只 add 自己路徑）＋push。
6. 啟動整夜：`cp native/bin/gpgp native/bin/gpgp-overnight; END=$(( $(date -d '2026-11-10 06:07' +%s) - $(date +%s) )); nohup systemd-run --user --scope --unit=arcagi-n3-gp -p MemoryMax=16G nice -n 19 timeout --signal=TERM --kill-after=60 $END native/gpu/gp/overnight.sh $PWD/reports/gpu-gp-1109/overnight "2026-11-10 06:00" &`；日誌 `reports/gpu-gp-1109/overnight/run.log`。

## 安全邊界與規則
照原交接書（寫入範圍、顯存 ≤4GB、`~/arcagi-STOP`、不改 N2 檔與 `arcagi-n2-overnight`）。新規：context 到 30% 就寫本檔換手。

## 補記（23:10）codex 已結束
- codex 回報：只新增 gp.hpp／gp_kernel.cu／gp_main.cpp（N2 檔與 Makefile 未改，`git status native/gpu` 已核）；`make -C native gpugp` 編譯成功、`native/bin/gpgp` 已產生。
- **沙箱內 GPU 不可用**，所以 smoke 沒有實際結果 → 接手者第一步：在沙箱外跑 smoke（3c9b0459 要 `solved:true`）並審 diff（隊長尚未審）。
- 三個 gp 原始檔已一併 commit（未審、未實跑），之後照審查結果修。
