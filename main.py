import time
import os
from datetime import datetime
from hyperliquid.info import Info
from hyperliquid.utils import constants
import requests
import signal
import sys

# 環境變數
WALLET = os.getenv("TARGET_WALLET", "0xb317d2bc2d3d2df5fa441b5bae0ab9d8b07283ae")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

info = Info(constants.MAINNET_API_URL, skip_ws=False)


def send_telegram(msg):
    """發送 Telegram 訊息"""
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print(f"⚠️ 推播失敗：缺少 TOKEN 或 CHAT_ID")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}

    try:
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code == 200:
            print(f"📱 已推播：{msg[:50]}...")
            return True
        else:
            print(f"推播失敗：{response.status_code}")
            return False
    except Exception as e:
        print(f"推播錯誤：{e}")
        return False


def format_time():
    """格式化當前時間"""
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


# 全域變數用於優雅關閉
total_alerts = 0


def signal_handler(sig, frame):
    """處理關閉信號"""
    shutdown_msg = (
        f"🛑 <b>監控服務已停止</b>\n\n"
        f"⏰ 停止時間：{format_time()}\n"
        f"📈 總共推播：<b>{total_alerts}</b> 則訊息"
    )
    send_telegram(shutdown_msg)
    print("\n👋 監控已停止")
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# 啟動訊息
startup_msg = (
    f"🦈 <b>雲端鯨魚雷達已啟動！</b>\n\n"
    f"📍 監控地址：<code>{WALLET[:10]}...{WALLET[-8:]}</code>\n"
    f"⏱ 檢查頻率：每 15 秒\n"
    f"🕐 啟動時間：{format_time()}"
)
send_telegram(startup_msg)

# 初始化
last_orders = {}
last_heartbeat = time.time()

print(f"✅ 監控已啟動 | 目標錢包：{WALLET}")

while True:
    try:
        # 獲取當前掛單
        open_orders = info.open_orders(WALLET)
        current = {o["oid"]: o for o in open_orders}
        alerts = []

        # 檢測新掛單
        for oid, o in current.items():
            if oid not in last_orders:
                sz = float(o["sz"])
                px = float(o["limitPx"])
                side = "買單" if o["side"] == "B" else "賣單"
                coin = o.get("coin", "Unknown")

                msg = (
                    f"🟥 <b>新掛單！</b>\n\n"
                    f"幣種：<b>{coin}</b>\n"
                    f"方向：{side}\n"
                    f"數量：<b>{sz:,.0f}</b> 張\n"
                    f"價格：<b>${px:,.2f}</b>\n"
                    f"時間：{format_time()}"
                )
                alerts.append(msg)
                send_telegram(msg)

        # 檢測訂單消失
        for oid, old in last_orders.items():
            if oid not in current:
                sz = float(old["sz"])
                px = float(old["limitPx"])
                side = "買單" if old["side"] == "B" else "賣單"
                coin = old.get("coin", "Unknown")

                msg = (
                    f"🟩 <b>訂單消失！</b>\n\n"
                    f"幣種：<b>{coin}</b>\n"
                    f"方向：{side}\n"
                    f"數量：<b>{sz:,.0f}</b> 張\n"
                    f"價格：<b>${px:,.2f}</b>\n"
                    f"狀態：→ 成交或取消\n"
                    f"時間：{format_time()}"
                )
                alerts.append(msg)
                send_telegram(msg)

        # 檢測部分成交
        for oid, o in current.items():
            if oid in last_orders:
                old_sz = float(last_orders[oid]["sz"])
                new_sz = float(o["sz"])

                if abs(old_sz - new_sz) > 1:
                    coin = o.get("coin", "Unknown")
                    px = float(o["limitPx"])
                    side = "買單" if o["side"] == "B" else "賣單"

                    msg = (
                        f"🟨 <b>部分成交！</b>\n\n"
                        f"幣種：<b>{coin}</b>\n"
                        f"方向：{side}\n"
                        f"價格：<b>${px:,.2f}</b>\n"
                        f"數量變化：<b>{old_sz:,.0f}</b> → <b>{new_sz:,.0f}</b> 張\n"
                        f"成交：<b>{abs(old_sz - new_sz):,.0f}</b> 張\n"
                        f"時間：{format_time()}"
                    )
                    alerts.append(msg)
                    send_telegram(msg)

        # 記錄偵測到的變化
        if alerts:
            total_alerts += len(alerts)
            print(f"{format_time()} | 偵測到 {len(alerts)} 個變化 | 累計：{total_alerts}")

        # 每小時心跳訊息
        if time.time() - last_heartbeat > 3600:
            heartbeat_msg = (
                f"💚 <b>系統運行正常</b>\n\n"
                f"⏰ 時間：{format_time()}\n"
                f"📊 目前監控：<b>{len(current)}</b> 個掛單\n"
                f"📈 累計推播：<b>{total_alerts}</b> 則訊息\n"
                f"✅ 狀態：正常運行中"
            )
            send_telegram(heartbeat_msg)
            last_heartbeat = time.time()
            print(f"💚 已發送心跳訊息")

        # 更新訂單快照
        last_orders = current

        # 等待 15 秒
        time.sleep(15)

    except Exception as e:
        error_msg = f"⚠️ <b>監控錯誤</b>\n\n錯誤訊息：<code>{str(e)}</code>\n時間：{format_time()}"
        send_telegram(error_msg)
        print(f"❌ 錯誤：{e}")
        time.sleep(30)