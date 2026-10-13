# 看懂圖表與保留結果

[實驗教學](README.md)｜[排錯](troubleshooting.md)

輸出目錄必須尚不存在，以免覆蓋或混合實驗。完成後會有：

- `report.html`：自含 SVG 圖表、方法比較、task × solver 成功率矩陣、tag 分組；不需網路或 CDN。
- `results.json`、`results.csv`：逐次保留方法、題目、seed、repeat、params、正確與否、test 分數、耗時、錯誤及 artifact 位置。
- `summary.csv`：各方法、各題／方法、各 tag／方法的次數、成功率、錯誤數及平均／中位耗時。
- `config.json`、`runs.jsonl`、`artifacts/`：設定快照、逐次追加紀錄、每次 request／response／stdout／stderr／run metadata。中途停止時可查已寫出的紀錄；完整報告於跑完後產生。

圖表的成功率是「答對整題的執行次數 ÷ 全部執行次數」。例如同一題跑四次只對一次就是 25%，不是 100%。多 test 題必須全部答對才算該次成功；timeout 和錯誤計入未成功次數。平均／中位耗時包含失敗程序以及程序與檔案處理成本，不是純演算法運算時間。

同一題可同時出現在多個 tag，tag 統計是重疊視角，不能相加當成整份資料集。CSV 中疑似試算表公式的文字會加單引號防止誤執行；原始文字完整保留在 JSON。需要重新處理資料時以 JSON 為準。

重現時保存程式 commit、編譯器／runtime 版本、設定檔與生成題 manifest。報告也保留經 schema 驗證後的 canonical JSON 題目內容 checksum（不是原檔 bytes checksum）；固定 seed 只在解法遵循 seed 且執行環境一致時有助重現。所有成績請標明公開 training、evaluation 或自訂／合成資料，不宣稱官方私有測試分數。
