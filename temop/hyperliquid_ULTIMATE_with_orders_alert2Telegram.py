# hyperliquid_telegram_alert.py  ← 最終手機即時推播版
import time
import pandas as pd
from datetime import datetime
from hyperliquid.info import Info
from hyperliquid.utils import constants
import requests

WALLET = "0xb317d2bc2d3d2df5fa441b5bae0ab9d8b07283ae"
info = Info(constants.MAINNET_API_URL, skip_ws=False)

# ↓↓↓ 這裡換成你自己的
TELEGRAM_TOKEN = "8341630301:AAFCeJv0CZyFG2V60l6jk4tnuZGNzcrb2Go"   # ← 換成 BotFather 給你的
CHAT_ID = "1132498345"                                          # ← 你的 Telegram 個人 ID（稍後教你怎麼拿）

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, data=payload, timeout=10)
    except:
        pass

# 第一次執行時會自動發一條測試訊息，幫你拿到 CHAT_ID
if CHAT_ID == "123456789":
    send_telegram("鯨魚雷達啟動！\n這條訊息的對話 ID 就是你的 CHAT_ID，複製數字貼回程式碼即可。")
    print("已發送測試訊息到 Telegram，請把收到的數字貼回 CHAT_ID 那行")
    exit()

last_orders = {}
print("鯨魚雷達 + Telegram 推播已啟動！任何變動立刻飛到你手機")

while True:
    try:
        open_orders = info.open_orders(WALLET)
        current = {o["oid"]: o for o in open_orders}
        alerts = []

        for oid, o in current.items():
            if oid not in last_orders:
                sz = float(o["sz"])
                px = float(o["limitPx"])
                side = "買單" if o["side"] == "B" else "賣單"
                msg = f"🟥 新掛單！\n{o['coin']} {side} {sz:,.0f} 張 @ ${px:,.2f}"
                alerts.append(msg)
                send_telegram(msg)

        for oid, old in last_orders.items():
            if oid not in current:
                sz = float(old["sz"])
                px = float(old["limitPx"])
                side = "買單" if old["side"] == "B" else "賣單"
                msg = f"🟩 訂單消失！\n{old['coin']} {side} {sz:,.0f} 張 @ ${px:,.2f}\n→ 已成交或取消"
                alerts.append(msg)
                send_telegram(msg)

        for oid, o in current.items():
            if oid in last_orders:
                old_sz = float(last_orders[oid]["sz"])
                new_sz = float(o["sz"])
                if abs(old_sz - new_sz) > 1:
                    msg = f"🟨 部份成交！\n{o['coin']} {old_sz:,.0f} → {new_sz:,.0f} 張"
                    alerts.append(msg)
                    send_telegram(msg)

        if alerts:
            print("\n" + "█"*50)
            for a in alerts:
                print(a.replace("🟥","★★★").replace("🟩","★★★").replace("🟨","★★★"))
            print("█"*50 + "\n")

        last_orders = current
        time.sleep(12)  # 12 秒一輪，手機秒收

    except Exception as e:
        send_telegram(f"⚠️ 程式錯誤：{e}")
        time.sleep(30)