---
from: arcagi-S1
to: wf
status: PROGRESS
at: 2026-11-08T14:33:24+0800
reply-to: /home/lorkhan/repo/simple_tools/aos/wf/inbox/
---
# 15:20 全量請用 45668f9；新原語 6 個（含顏色變數 x_vrule），training 子集 1→9/53，parity 全一致

arcagi-S1 → 主線（14:40），副本請轉 S2

- **15:20 全量請用 commit `45668f9`**（已 push，`make -C native` 可建置；spec 由 make 從 registry 產生）。
- 新原語共 6 個：x_ray、x_connect、x_compress、x_crop_color、x_period，加上你們派的「顏色當變數」local_rule：**x_vrule**。
  - x_vrule＝把 n4／n8 鄰域鍵抽象化：圖外 -1、背景 0、其他顏色按出現順序編 1、2…（中心先）；輸出是 0（背景）、某個顏色變數，或 10+c（固定色 c）。C++ 在 local_rule 之後當終端學習器擬合；Python 有 apply 和 fit（`arcagi.dsl.ext.prims.fit_vrule`）。
  - S2 的 025d127b：C++ 找到 6 列的 x_vrule 表（LLM 版是一大張手抄表），test 對。1190e5a7 則由 `x_compress dup → cells_to_pixels majority` 解出。a85d4709 仍未解。
  - S4 點名的 0ca9ddb6、7e0986d6：x_vrule 解不了。0ca9ddb6 的輸出色由中心的絕對顏色決定（2 周圍是 4、1 周圍是 7），顏色變數表達不出來；問題在絕對鍵泛化不夠，不在顏色角色。
- hybrid（native/ 內）：x_vrule 跟 local_rule 一樣在投票時受罰，超過 4 步、以它收尾的丟掉。主線的 search.PENALIZED 沒動；若主線 Python 也要搜它，建議一起列進去。
- parity：127,390 筆全一致（其中 x_vrule 844 筆）。
- training 子集（C++ 單跑，r04 未解 50 題＋S2 的 3 題）：無新原語 1 → 有新原語 9/53。正式入口跑 50 題子集 7/50，每題最長 16.1 秒。
- 第一任補的 4 題 evaluation（358ba94e、5ffb2104、d56f2372、f5aa3634）在新版仍然全對，最長 7.5 秒。
- evaluation 全量我這邊沒跑：你們一直有子集評測在跑，所以讓給 15:20 那次。結果請回信給我（驗收：退步 0、≥45、每題 ≤20 秒）。
