# hyperliquid_telegram_final.py  ← 自動拿到 chat_id + 永久推播
import time
import requests
from datetime import datetime
from hyperliquid.info import Info
from hyperliquid.utils import constants

WALLET = "0xb317d2bc2d3d2df5fa441b5bae0ab9d8b07283ae"
info = Info(constants.MAINNET_API_URL, skip_ws=False)

# ↓↓↓ 只要換這一行！BotFather 給你的 token
TOKEN = "8341630301:AAFCeJv0CZyFG2V60l6jk4tnuZGNzcrb2Go"   # ← 換成你自己的

# 不用管下面的，第一次跑會自動拿到 chat_id 並存檔
ID_FILE = "telegram_chat_id.txt"
if open(ID_FILE, "a+", encoding="utf-8").close() or True:
    try:
        with open(ID_FILE, "r", encoding="utf-8") as f:
            CHAT_ID = f.read().strip()
    except:
        CHAT_ID = None

def send(msg):
    if not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
    try:
        requests.post(url, data=payload, timeout=8)
    except:
        pass

# 第一次啟動：強制發一條訊息拿到 chat_id
if not CHAT_ID:
    print("第一次啟動，正在強制取得你的 Telegram chat_id…")
    # 發一條「測試」訊息給自己（你必須先跟 Bot 說過一次話）
    temp_msg = "鯨魚雷達啟動！\n請回覆任意訊息給我，我會告訴你 chat_id"
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                  data={"chat_id": "me", "text": temp_msg})  # 特殊用法會發給 Bot 主人
    
    print("請打開 Telegram 跟你的 Bot 說一句「hi」或任意字")
    print("30 秒內會自動拿到 chat_id 並存檔，之後就永久推播了！\n")
    
    # 輪詢 getUpdates 直到拿到
    for _ in range(30):
        try:
            upd = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates").json()
            for u in upd["result"][::-1]:
                if "message" in u and u["message"].get("text"):
                    CHAT_ID = str(u["message"]["chat"]["id"])
                    with open(ID_FILE, "w", encoding="utf-8") as f:
                        f.write(CHAT_ID)
                    send(f"chat_id 已自動儲存：{CHAT_ID}\n從現在起任何鯨魚動作都會即時推播！")
                    print(f"成功拿到 chat_id：{CHAT_ID} 已存檔！")
                    break
        except:
            pass
        time.sleep(1)

send("鯨魚雷達正式啟動！")

# ==================== 以下是原本的監控邏輯 ====================
last_orders = {}

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
                msg = f"新掛單！\n{o['coin']} {side} {sz:,.0f} 張 @ ${px:,.2f}"
                alerts.append(msg)
                send(msg)

        for oid, old in last_orders.items():
            if oid not in current:
                sz = float(old["sz"])
                px = float(old["limitPx"])
                side = "買單" if old["side"] == "B" else "賣單"
                msg = f"訂單消失！\n{old['coin']} {side} {sz:,.0f} 張 @ ${px:,.2f}\n→ 已成交或取消"
                alerts.append(msg)
                send(msg)

        for oid, o in current.items():
            if oid in last_orders:
                old_sz = float(last_orders[oid]["sz"])
                new_sz = float(o["sz"])
                if abs(old_sz - new_sz) > 1:
                    msg = f"部份成交！\n{o['coin']} {old_sz:,.0f} → {new_sz:,.0f} 張"
                    alerts.append(msg)
                    send(msg)

        if alerts:
            print("\n" + "█"*60)
            for a in alerts:
                print(f"★★★ {a} ★★★")
            print("█"*60 + "\n")

        last_orders = current
        time.sleep(12)

    except Exception as e:
        send(f"程式錯誤：{e}")
        time.sleep(20)