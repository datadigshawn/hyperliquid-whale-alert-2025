# hyperliquid_FINAL_NO_ERROR.py  ← 這次真的最後一次了
import time
import pandas as pd
from datetime import datetime
from hyperliquid.info import Info
from hyperliquid.utils import constants

WALLET = "0xb317d2bc2d3d2df5fa441b5bae0ab9d8b07283ae"
info = Info(constants.MAINNET_API_URL, skip_ws=False)

order_file = "hyperliquid_0xb317_orders.csv"
last_orders = {}          # 用來比對變化

print("【最終無敵版】鯨魚委託單雷達啟動")
print("任何掛單、減單成交取消 → 立刻紅字大喊！\n")

while True:
    try:
        now = datetime.now()

        # ==================== 當前委託單 ====================
        open_orders = info.open_orders(WALLET)

        current = {}
        alerts = []

        for o in open_orders:
            oid = o["oid"]
            current[oid] = o

            # 新單
            if oid not in last_orders:
                coin = o.get("coin", "Unknown")
                sz   = float(o["sz"])
                px   = float(o["limitPx"])
                side = "買單" if o["side"] == "B" else "賣單"
                alerts.append(f"新掛單！ {coin} {side} {sz:,.0f} 張 @ ${px:,.2f}")

        # 消失的單（成交或取消）
        for oid, old in last_orders.items():
            if oid not in current:
                coin = old.get("coin", "Unknown")
                sz   = float(old["sz"])
                px   = float(old["limitPx"])
                side = "買單" if old["side"] == "B" else "賣單"
                alerts.append(f"訂單消失！ {coin} {side} {sz:,.0f} 張 @ ${px:,.2f} → 成交或取消")

        # 數量變動（被部份吃掉）
        for oid, o in current.items():
            if oid in last_orders:
                old_sz = float(last_orders[oid]["sz"])
                new_sz = float(o["sz"])
                if abs(old_sz - new_sz) > 1:
                    coin = o.get("coin", "Unknown")
                    alerts.append(f"部份成交！ {coin} {old_sz:,.0f} → {new_sz:,.0f} 張")

        # 印出警報
        if alerts:
            print("\n" + "█"*100)
            for a in alerts:
                print(f"\033[91m★★★ {a} ★★★\033[0m")
            print("█"*100 + "\n")

        # 存檔
        if open_orders:
            df = pd.DataFrame(open_orders)
            df["check_time"] = now.strftime("%Y-%m-%d %H:%M:%S")
            header = not pd.io.common.file_exists(order_file)
            df.to_csv(order_file, mode="a", header=header, index=False)

        last_orders = current

        # 簡單顯示目前掛單數量
        print(f"{now.strftime('%H:%M:%S')} | 目前掛單 {len(open_orders)} 筆 | 監控中…")
        if open_orders:
            print(pd.DataFrame(open_orders)[["coin","side","sz","limitPx"]].to_string(index=False))

        print("\n" + "-"*100)
        time.sleep(15)

    except Exception as e:
        print(f"錯誤：{e}，20 秒後重試")
        time.sleep(20)