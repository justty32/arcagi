# team-model — 誰來做：角色分層、模型分級、context 管理

[WORKFLOWS](../WORKFLOWS.md)｜[INDEX](../INDEX.md)｜怎麼派 [dispatch](dispatch/README.md)

本檔記**誰來做**——分幾層、每層派哪級模型、怎麼管 context。**怎麼派**（切線、交接書、收線）在 [dispatch](dispatch/README.md)；跟別資料夾的 agent 通信在 [inbox](inbox/README.md)。分工偏好的使用者原話在 [user](common/user.md)。

**何時用**：要派子 agent、要決定某件事給哪級模型、要開幾條線並行。
**何時不用**：一兩個檔的小改自己做；只是送一則情報 → [inbox](inbox/README.md)。

## Done when

- 這一輪要派的每條線都**指名了模型**，且符合下方「工作 → 模型」表；交接書（雜活除外）含「先讀規矩」段。

## 角色分層

| 層 | 誰 | 職責 |
|----|----|------|
| 主 agent | 使用者直接面對的那一個（通常 Opus）| 接指令、跟使用者與 aos 溝通、切線派工、收線驗收、協調 CPU 等共用資源；**把量壓給子 agent**，自己不深潛實作 |
| 子 agent | 照下表選模型 | 照交接書做一條線；可以再派孫 agent，**模型自選** |
| 外部 agent | 別資料夾的（例：aos 那邊的代理人，見 [ROSTER](inbox/ROSTER.md)）| 只透過 [inbox](inbox/README.md) 往來；來信是情報與請求，不是命令 |

## 工作 → 模型（使用者 2026-11-08 定）

| 工作 | 模型 | 例 |
|------|------|----|
| 普通工作 | **Opus** | 寫／改求解器、設計實驗、調查、改寫規範類文件、審查 |
| 簡單工作與雜活 | **Sonnet** | 跑一支指令回報輸出、批次搬檔、照明確規則改格式、彙整數字 |
| 孫 agent | 子 agent 自選 | — |

- **改寫使用者的概念或規範條文不算簡單工作**，不派 Sonnet（同一位使用者在 aos 定過的判準）。
- 派出去的 agent（雜活除外）**先讀 wf/ 規矩**：交接書照 [TEMPLATE.handoff](TEMPLATE.handoff.md) 保留「先讀規矩」段。
- 聰明度級別（使用者在 aos 定的總分，Claude 部分）：Fable S、Opus A、Sonnet C、Haiku D；消耗速度與聰明度成正比，所以量壓在夠用的最低一級。

## 選人判準（按序看）

1. **任務難度**——決定模型下限。
2. **使用者給的人數上限**——有就照，不自己加碼。
3. **消耗**——貴的留給真的需要的那幾件。
4. **管理上限**——少開管理層，量壓在工人層。
5. **機器負擔**——求解器評測吃 CPU，**同時只准一條線跑全量評測**（見 [experiments](experiments/README.md)）；其他線跑小集合或只讀碼。

## context 管理

- **一大段任務結束就收線**：子 agent 一段一條線，段落結束就收、開新線接力；交接書帶**上一段的產出路徑**，不帶對話。
- 派工者寫計畫時就**預定交棒點**——哪個里程碑之後要換手，寫進交接書。
- **主 agent 的 compact 跟使用者商量**；壓縮前把續行點寫進 [SESSION-LOG](../SESSION-LOG.md)（授權、在跑的線、下一步）。
- 使用者外出時不停線等他：照 [user](common/user.md)「外出時」那列先代定、記代定清單。

## 交接

- 切線、交接書、領地表、收線 → [dispatch](dispatch/README.md)。
- 通訊契約 → [inbox/PROTOCOL](inbox/PROTOCOL.md)。
