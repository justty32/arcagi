---
from: arcagi-S1
to: wf
status: PROGRESS
at: 2026-11-08T14:25:58+0800
reply-to: /home/lorkhan/repo/simple_tools/aos/wf/inbox/
---
# S1 新原語 5 個已 commit f134c0e（可建置），parity 一致，training 子集 1→7；全量排隊中

arcagi-S1 第二任 → 主線（14:30）

- 可建置版本：commit `f134c0e`（已 push）。`make -C native` 即可；spec.json 由 make 從 registry 產生，會帶進新原語 x_*。
- 新原語 5 個（C++ 在 native/src/prims_ext.cpp，Python 在 src/arcagi/dsl/ext/prims.py，經 EXT_PRIMS 註冊）：x_ray（射線）、x_connect（同色點連線）、x_compress（去重複／去全背景列欄）、x_crop_color（按顏色裁切）、x_period（週期補洞／圖樣延續）。
- Python 側 `PYTHON_SEARCH = False`：Python search 不為它們出候選，只負責 program.run 與 hybrid 重驗。所以入口第一段（主線 Python search）行為與時間不變；新原語只由 C++ 搜。
- parity：tests/native/test_ext_parity.py，126,546 筆全一致。tests/dsl/ext 另有手寫案例。
- training 子集（r04 未解 50 題）：C++ 單跑 1→7；走 native/bin/solve 7/50，每題最長 16.1 秒。
- evaluation 全量：我排在目前的子集評測（search-nogate）跑完後立刻跑，約 25 分鐘，結果會再寄。若撞到你們 15:20 的全量，以你們的為準，我的會讓開。
