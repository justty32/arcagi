# think-5 progress（GPU 同步次數：跨題合批／多層融合）

主題：「一次 GPU 同步涵蓋多題／多層」能否讓 GPU 端到端贏 CPU。流程只到 02b（E10 精神：不寫 03、不施工）。

## 第一棒（t5，11-10）

- [完] 01-簡報（隊長親寫）：同步模型 s·λ vs W_g；1e6 打平需 λ<1.7 ms，實測 27 ms（汙染）；合批封頂 1.35×、融合必綁 lambda kernel；GPU 同卡 8 行程、Default 時間切片。
- [完] 02 fable（Agent model=fable，非 `claude -p`；73 行）：A 先量乾淨 λ＋整層預發／重疊、B 合批排程器（先 B0 量 N_eff）、C 整列舉器上 GPU 綁 L1。推薦閘 0（量 λ_clean）。另更正 01 §4a「提高 P」不改比值。
- [完] 02b Argon（15.7 KB，無 auth 錯）：P0×3（A2 兩遍走訪破 0 mismatch；模型漏 sync_s／chunk 數；5.4 ms 門檻犯均值代換），另更正 01 F3 Amdahl 表述（已改 01）。呼叫：`cd /tmp && agy -p <全文> --model "Gemini 4 Argon (High)" --mode plan --print-timeout 840s`；腳本 `/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/t5/run-argon.sh`，輸出 `.../t5/argon-out.md`、stderr `.../t5/argon-err.log`。
- [完] 代定清單 G1–G15（含 Argon 處置）＋「要使用者裁」5 條。
- 本輪止於 02b；不寫 03、不施工。

## 下一步（使用者）

- 排 10–15 分鐘乾淨 GPU 窗口跑 A0 λ 微基準（閘 0）；裁 E1 衝突、E5 門檻。見 `代定清單.md`「要使用者裁」。
