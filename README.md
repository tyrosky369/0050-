# 🌡️ 0050 溫度計

元大台灣 50 ETF（0050）市場溫度儀錶盤 — 一個介於 0~100 的「市場溫度值」，協助投資人判斷買賣時機。

![溫度區間](https://img.shields.io/badge/溫度_0--20-極度低溫-1D4ED8) ![](https://img.shields.io/badge/20--40-偏低溫-60A5FA) ![](https://img.shields.io/badge/40--60-正常-10B981) ![](https://img.shields.io/badge/60--80-偏高溫-F59E0B) ![](https://img.shields.io/badge/80--100-極度過熱-EF4444)

## 功能特色

| 面向 | 指標 | 權重 |
|------|------|------|
| 技術面 (50%) | RSI・KD・MACD・乖離率・布林通道・量均比 | 各 5–12% |
| 籌碼面 (50%) | 外資買賣超・融資餘額・融券餘額・大戶持股・受益人數 | 各 7–15% |

- 資料來源：TWSE 臺灣證券交易所（即時 T+0/T+1）
- 每日自動快取，啟動後秒速回應
- 90 日歷史走勢圖（股價 + 技術面溫度）

## 本地開發

### 需求
- Python 3.9+
- Node.js 18+

### 後端
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
# API: http://localhost:8000
```

### 前端
```bash
cd frontend
npm install
npm run dev
# Web: http://localhost:5173
```

> 首次啟動需約 30~60 秒從 TWSE 抓取籌碼資料（之後快取每日更新）

## 部署（免費）

### 方法一：Render（最簡單）

1. 推送到 GitHub
2. 前往 [render.com](https://render.com) → New → Blueprint
3. 選擇你的 repo，Render 會自動讀取 `render.yaml`
4. 後端部署完成後，複製後端網址（如 `https://0050-thermometer-api.onrender.com`）
5. 在前端服務的 Environment Variables 設定 `VITE_API_URL = <後端網址>`
6. 在後端服務的 Environment Variables 設定 `ALLOWED_ORIGINS = <前端網址>`

### 方法二：Vercel（前端）+ Render（後端）

**後端 → Render**
1. New Web Service → 選 repo → Root Directory: `backend`
2. Build: `pip install -r requirements.txt`
3. Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`

**前端 → Vercel**
1. Import repo → Root Directory: `frontend`
2. Environment Variable: `VITE_API_URL = <Render 後端網址>`

## 免責聲明

本工具僅供學習研究使用，不構成任何投資建議。投資前請自行評估風險。
