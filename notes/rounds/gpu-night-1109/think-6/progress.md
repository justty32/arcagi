# think-6 progress（GPU 窮舉當主線候選來源：下一步）

流程只到 02b＋代定（不寫 03、不施工）。

- [完] 01-簡報（隊長親寫）：208 題「≥0.9 未解」中 161 題 gain≤0.001（≈原樣輸出），gain>0.05 僅 25 題、6 題已全對、3 題 test 對且已被 N4f 拿走；天花板兩 split 0～3、training 0～1。主線成本：多數放棄題是預算型（out_of_budget 188／293，停 d3，約 12.5 s、max_nodes 2e6 先撞），提早停型僅 13／8。腳本 scratchpad `t6/an.py`、`t6/tr.py`（輸出 `.out`）。
- [完] 02 fable（Agent model=fable，62 行）：B 不冗餘門 → A d6 定向 13 題 → C seeds；D CPU 提早停並行；預期合計 0～2。
- [完] 02b Argon（14 KB，exit 0）：P0×3（B 規則偷看 eval 66e6c45b；A 母體混入已全對題；小樣本假紅／過擬合），翻 H7（C 不鎖在 A 後）。呼叫：scratchpad `t6/run-argon.sh`（`agy -p … --model "Gemini 4 Argon (High)" --mode plan`），輸出 `t6/argon-out.md`。
- [完] 代定清單 H1–H12＋Argon 處置＋要使用者裁 3 條。

## 結論

推薦 B（先驗定義的不冗餘／前綴化約門，CPU 分鐘級）＋補完 20 s 未完 d5 的題，再決定 A／無記表 C；預期再多 0～2 題（training 0～1）。要使用者裁：這條線是否值得繼續、`ARCAGI_GPU_FALLBACK` 是否轉預設開、是否准做 D（主線 search.cpp 提早停規則）的 training 回歸實驗。
