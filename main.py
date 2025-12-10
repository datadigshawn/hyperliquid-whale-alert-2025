import time
import os
from datetime import datetime
from hyperliquid.info import Info
from hyperliquid.utils import constants
import requests

# 環境變數（Render 會自動填）
WALLET = os.getenv("TARGET_WALLET", "0xb317d2bc2d3d2df5fa441b5bae0ab9d8b07283ae")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

info = Info(constants.MAINNET_API_URL, skip_ws=False)

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print(f"⚠️ 推播失敗：缺少 TOKEN 或 CHAT_ID")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
    try:
        requests.post(url, data=payload, timeout=10)
        print(f"📱 已推播：{msg}")
    except Exception as e:
        print(f"推播錯誤：{e}")

# 啟動訊息
send_telegram(f"🦈 雲端鯨魚雷達已啟動！\n監控地址：{WALLET}\n每 15 秒檢查一次訂單變化")

last_orders = {}

while True:
    try:
        open_orders = info.open_orders(WALLET)
        current = {o["oid"]: o for o in open_orders}
        alerts = []

        # 新單
        for oid, o in current.items():
            if oid not in last_orders:
                sz = float(o["sz"])
                px = float(o["limitPx"])
                side = "買單" if o["side"] == "B" else "賣單"
                coin = o.get("coin", "Unknown")
                msg = f"🟥 新掛單！\n{coin} {side} {sz:,.0f} 張 @ ${px:,.2f}"
                alerts.append(msg)
                send_telegram(msg)

        # 消失單
        for oid, old in last_orders.items():
            if oid not in current:
                sz = float(old["sz"])
                px = float(old["limitPx"])
                side = "買單" if old["side"] == "B" else "賣單"
                coin = old.get("coin", "Unknown")
                msg = f"🟩 訂單消失！\n{coin} {side} {sz:,.0f} 張 @ ${px:,.2f}\n→ 成交或取消"
                alerts.append(msg)
                send_telegram(msg)

        # 部份成交
        for oid, o in current.items():
            if oid in last_orders:
                old_sz = float(last_orders[oid]["sz"])
                new_sz = float(o["sz"])
                if abs(old_sz - new_sz) > 1:
                    coin = o.get("coin", "Unknown")
                    msg = f"🟨 部份成交！\n{coin} {old_sz:,.0f} → {new_sz:,.0f} 張"
                    alerts.append(msg)
                    send_telegram(msg)

        if alerts:
            print(f"{datetime.now()} | 偵測到 {len(alerts)} 個變化")

        last_orders = current
        time.sleep(15)  # 15 秒一輪

    except Exception as e:
        send_telegram(f"⚠️ 監控錯誤：{e}")
        time.sleep(30)
