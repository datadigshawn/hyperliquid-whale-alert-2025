# 🦈 Whale Tracker — Hyperliquid 巨鯨追蹤系統

監控指定錢包在 Hyperliquid 交易所的 **開倉/平倉/部分成交** 動作，即時推播到 Telegram。

---

## 📁 檔案結構

```
whalexxx/
├── README.md              ← 本檔案
├── main.py                ← 主程式（監控 open_orders + 推 Telegram）
├── requirements.txt       ← Python 依賴
├── .env                   ← 設定（錢包 / Bot token / Chat ID）
├── .venv/                 ← 本地 Python venv
├── whale.log              ← launchd stdout
└── whale.error.log        ← launchd stderr
```

> `temop/` 是開發時的舊版本程式碼，可忽略。

---

## ⚙️ 目前配置

| 項目 | 值 |
|------|---|
| 監控錢包 | `0x9d32884370875f2960d5cc4b95be26687d69aff5` |
| Bot | **@whale9527_bot**（whaleBot） |
| 推播目的地 | 你的 DM（chat_id `1132498345`） |
| 檢查頻率 | 每 **15 秒** |
| 心跳訊息 | 每 **1 小時** |
| 自動啟動 | ✅ launchd（`com.whale.tracker`） |

---

## 🔔 會推播哪些事件

| 事件 | Emoji | 說明 |
|------|-------|------|
| **新掛單** | 🟥 | 鯨魚剛掛了新訂單（幣種、方向、數量、價格） |
| **訂單消失** | 🟩 | 訂單從簿子上消失 → 成交或取消 |
| **部分成交** | 🟨 | 訂單數量變化 > 1 張 |
| **心跳** | 💚 | 每小時一次，確認系統運作中 |
| **啟動/停止** | 🦈 / 🛑 | 服務啟動與關閉通知 |
| **錯誤** | ⚠️ | 監控過程出錯（API 失敗等） |

---

## 🚀 指令

```bash
cd /Users/shawnclaw/autobot/whalexxx
VENV=.venv/bin/python

# 手動測試
$VENV main.py

# 看即時 log
tail -f whale.log

# launchd 控制
launchctl list | grep whale                                      # 查狀態
launchctl unload ~/Library/LaunchAgents/com.whale.tracker.plist  # 停止
launchctl load ~/Library/LaunchAgents/com.whale.tracker.plist    # 啟動
launchctl kickstart -k "gui/$(id -u)/com.whale.tracker"          # 重啟
```

---

## 🔧 修改追蹤目標

編輯 `.env`：

```bash
TARGET_WALLET=0x新錢包地址
TELEGRAM_TOKEN=bot_token
TELEGRAM_CHAT_ID=chat_id
```

然後重啟：
```bash
launchctl kickstart -k "gui/$(id -u)/com.whale.tracker"
```

---

## 🔗 API 相關

**Hyperliquid 當前持倉查詢：**
```bash
curl -X POST https://api.hyperliquid.xyz/info -H "Content-Type: application/json" \
  -d '{"type":"clearinghouseState","user":"0x9d32884370875f2960d5cc4b95be26687d69aff5"}'
```

**Open orders：**
```bash
curl -X POST https://api.hyperliquid.xyz/info -H "Content-Type: application/json" \
  -d '{"type":"openOrders","user":"0x9d32884370875f2960d5cc4b95be26687d69aff5"}'
```

**歷史成交：**
```bash
curl -X POST https://api.hyperliquid.xyz/info -H "Content-Type: application/json" \
  -d '{"type":"userFills","user":"0x9d32884370875f2960d5cc4b95be26687d69aff5"}'
```

---

## 📝 Changelog

| 日期 | 變更 |
|------|------|
| 2026-04-15 | 從 `datadigshawn/hyperliquid-whale-alert-2025` clone 遷入本地 |
| 2026-04-15 | 換用 @whale9527_bot + 新監控錢包 0x9d32...aff5 |
| 2026-04-15 | 本地 .venv + .env 自動載入 + launchd 常駐 |
