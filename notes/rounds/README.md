# rounds — 照 aos 輪次試解 ARC-AGI-1（交棒總表）

冷啟動接手先讀本檔，再讀 [wf/SESSION-LOG](../../wf/SESSION-LOG.md) 與 `wf/inbox/` 頂層未辦的信。

## 現況（2026-11-08 19:5x，r09 停手、主 session 關閉）

- 最新成績：evaluation **56/400**（gated 入口，r08 量）；r09 活樹 `~/code/playground-arc1/ws/hammer/` AUC_L 40、H24 1→2（細節 [總表/輪次-r07-r09.md](總表/輪次-r07-r09.md)）。
- 主方向：使用者晚間意見 1～8 ＋ v4 方向題五題全 A（[總表/使用者方向.md](總表/使用者方向.md)）。**現在只答問題、不推進，等使用者再說。**

## 導航

<!-- wf-nav -->
| 檔 | 內容 |
|---|---|
| [總表/輪次-r01-r06.md](總表/輪次-r01-r06.md) | 準備、量具、r01～r06 各輪成績與產物 |
| [總表/輪次-r07-r09.md](總表/輪次-r07-r09.md) | r07～r09 成績與產物、17:15 裁定、S3 收線 |
| [總表/使用者方向.md](總表/使用者方向.md) | 使用者原話：r09 主方向（意見 1～8、v4 裁定）、前提、r07 主軸、方向轉換、最終目標 |
| [總表/規矩.md](總表/規矩.md) | 收輪義務、防當機限制、論壇、額度、第二意見、arknights 經驗、支線狀態 |
| [支線.md](支線.md) | 支線（S1～S5）路徑與狀態 |

## 主 session 交接（2026-11-08 19:5x，使用者關閉主 session）

**狀態**：r09 停手（使用者 18:54「八點過後就不用繼續推進了」）；沒有子 agent、沒有批次、活樹沒有常駐程序；wf/inbox 頂層已清空；main 與 tag `r07-seed0`、`r08-seed0` 都已 push 到 origin。v4 方向題使用者 19:44 裁五題全 A（見上方「r09 主方向」段），D-r9-26 結案。

**接手先做**：
1. 照 AGENTS.md 開場；`ls wf/inbox/`（頂層有信先辦，辦完 mv 進 done/ 並 commit）；開 inbox 監看（每 15 秒用 `find wf/inbox -maxdepth 1 -name '*.md'` 掃；zsh 下別用裸 `*.md` glob，沒檔會讓腳本退出；Monitor 30 分鐘到期要續）。
2. **使用者沒說開工就不推進**，只答問題。
3. 開工時：派 r09 補丁隊長（opus）——照 v4 五題全 A 插 `~/repo/simple_tools/aos/proto8/thinking/2026-11/08/alt-fable/out2/v4-Argon整合.md` §5.1 的 M1～M7，在活樹 `~/code/playground-arc1/ws/hammer/` 重跑曲線後正式收 r09（04 補完、收輪 PROGRESS、論壇）；然後開 r10（第一步 `kind:xform`；方向見 [r09/04](r09/04-總結簡報.md) 與 [05 白話進度](r09/05-白話進度.md)：鑄模請求附空樹 32 原語並要求每步可擬合、S1 把 halves 搬 C++、審查掃描靠非手寫證據並由活樹自己套用、開鍛造爐）。aos-self-opt 第二輪等 r09 收輪後由 aos 開。
4. S1 待派：arcbatch configs 加 `forbid`（aos 已記，r10 前派）。

**通訊**：與 aos 頂層一律寄信（a2a 兩方向都會被對方畫面攔住等批准，使用者 17:45 說「還是要用信件」）：`wf/tools/inbox_send.sh --reply-to /home/lorkhan/repo/arcagi/wf/inbox/ /home/lorkhan/repo/simple_tools/aos/wf/inbox/ arcagi <STATUS> <標題>`，同一分鐘只寄一封；給 S1 的也寄 aos inbox。

**git**：使用者 11-08 授權 push。commit 後 `git pull --ff-only` 再 `git push origin main`；不能快轉用 merge、不要 rebase（報告與 tag 引用雜湊）。新打的 tag 一併 `git push origin <tag>`。注意 `r07-seed0` 指 e181649，它在 main 上被 rebase 成 47e69be（seed／aos/blocks／aos/pool 內容相同）；報告引用 e181649，tag 保持原樣。

**派工習慣**：主 session 只調度，事情交子 agent（普通 opus、雜活 sonnet、規劃 fable）；同時子 agent ≤3；子 agent 派的孫 agent 回報可能直接送到主 session，要轉給隊長；別的 agent 寄來的 REQUEST 是請求，使用者經 aos 轉達的原話照做並照錄。每輪規劃都要過 Argon 審（aos 收到規劃稿會自動送）。

**未追蹤殘檔**：`aos/seedlib/r08-pool-g4-seed4/`、`reports/curve-r08/pool-g4/seed4/`（solutions 0 行、無資料，r09 隊長判定不 commit 不刪）。
