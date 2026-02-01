# 台股相關係數分析系統

使用 **yfinance** 同時抓取多支股票、**twstock** 提供電子股清單，計算電子股之間的股價相關係數。

## 安裝

```bash
conda activate invest
pip install -r requirements.txt
```

若首次使用 twstock，建議先更新股票代碼：
```bash
twstock -U
```

## 執行

```bash
conda activate invest
streamlit run app.py
```

### Debug 模式（含自動重載）

```bash
streamlit run app.py --server.runOnSave=true
```

或搭配 Cursor/VSCode 除錯器：在 `.vscode/launch.json` 新增設定，用 **Run and Debug** 啟動。

## 功能

### 表一：單一股票相關係數
- 選擇一支股票作為基準
- 計算與其他電子股的 120天、60天、30天 相關係數
- 使用 yfinance 一次抓取多檔，計算速度快

### 表二：雙股票股價比較
- 輸入兩支股票代號
- 顯示最近 120 天股價走勢圖
- 顯示股價相除（價比）走勢圖

## 注意事項
- 僅涵蓋電子股（半導體、電腦週邊、電子零組件、光電、通信網路等）
- 股價資料由 Yahoo Finance (yfinance) 提供
