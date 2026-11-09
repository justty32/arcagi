# N5b seed GPU 一層：進度

狀態：完成（驗收 3 條都過）。

- 做到：`native/gpu/seed/{gpuseed.hpp,kernel.cu,host.cpp}`、`native/Makefile` 追加 `gpuseed` 目標、`native/bin/gpuseed`、`tests/native/test_gpuseed.py`、`report.md`。
- 數字：2–6 層 100 題指紋集合與節點數 GPU==CPU（0 不一致）；吞吐比（kernel 平均 / CPU 4 執行緒）L2 0.13×、L3 2.6×、L4 7×、L5 16×、L6 30×。
- 下一步（未做）：warp 協作 grid 雜湊（小層長尾）；把勝者物化進 GPU bank 以連跑多層；lambda 原語（BodyPool × 元素）定長 kernel。
- 背景單元：無。
