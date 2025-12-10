# coinGlassTrack_hyperliquid_ULTIMATE.py  ← 終極防呆版（永不崩潰）
import time
import pandas as pd
from datetime import datetime
from hyperliquid.info import Info
from hyperliquid.utils import constants

WALLET = "0xb317d2bc2d3d2df5fa441b5bae0ab9d8b07283ae"
info = Info(constants.MAINNET_API_URL, skip_ws=False)

pos_file = "hyperliquid_0xb317_positions.csv"
trade_file = "hyperliquid_0xb317_trades.csv"

ALERT_THRESHOLD = 100000
last_total_pnl = None

print(f"開始追蹤超級鯨魚：{WALLET}")
print("每 45 秒更新一次，按 Ctrl+C 停止\n")

while True:
    try:
        now = datetime.now()

        # 1. 持倉
        state = info.user_state(WALLET)
        raw_positions = state.get("assetPositions", [])
        withdrawable = float(state.get("withdrawable", 0))

        records = []
        total_pnl = 0.0

        if not raw_positions:
            print(f"{now.strftime('%H:%M:%S')} │ 完全沒持倉 │ 可提領 ${withdrawable:,.0f}")
        else:
            for item in raw_positions:
                # 超級防呆取值
                coin = item.get("coin") or item.get("asset") or f"Unknown_{item.get('asset', 'N/A')}"
                pos = item.get("position", {})

                size_str = pos.get("szi", "0")
                entry_str = pos.get("entryPx", "0")
                pnl_str = pos.get("unrealizedPnl", "0")

                try:
                    size = float(size_str)
                    entry = float(entry_str)
                    unrealized = float(pnl_str)
                except:
                    size = entry = unrealized = 0.0

                leverage = 1
                if "leverage" in pos:
                    if isinstance(pos["leverage"], dict):
                        leverage = pos["leverage"].get("value", 1)
                    else:
                        leverage = float(pos["leverage"] or 1)

                mark = item.get("markPx")
                mark_price = float(mark) if mark else 0.0

                total_pnl += unrealized

                records.append({
                    "time": now.strftime("%Y-%m-%d %H:%M:%S"),
                    "coin": coin,
                    "side": "LONG" if size > 0 else "SHORT",
                    "size": abs(size),
                    "entry_price": entry,
                    "mark_price": mark_price,
                    "unrealized_pnl": round(unrealized, 2),
                    "leverage": leverage,
                    "total_pnl": round(total_pnl, 2),
                    "withdrawable": withdrawable
                })

            df_pos = pd.DataFrame(records)

            # 警報
            if last_total_pnl is not None:
                diff = total_pnl - last_total_pnl
                if abs(diff) >= ALERT_THRESHOLD:
                    arrow = "暴漲" if diff > 0 else "暴跌"
                    color = "\033[92m" if diff > 0 else "\033[91m"
                    print(f"\n{color}★★★ {arrow} ${abs(diff):,.0f} ★★★ 目前 ${total_pnl:,.0f}\033[0m\n")

            last_total_pnl = total_pnl

            print(f"\n{now.strftime('%H:%M:%S')} │ 總未實現 ${total_pnl:,.0f} │ 可提領 ${withdrawable:,.0f}")
            print(df_pos[['coin','side','size','entry_price','unrealized_pnl','leverage']])

            # 存檔
            header = not pd.io.common.file_exists(pos_file)
            df_pos.to_csv(pos_file, mode='a', header=header, index=False)

        # 2. 最近交易
        try:
            trades = info.user_fills(WALLET)
            if trades and len(trades) > 0:
                df_t = pd.DataFrame(trades)
                df_t['time'] = pd.to_datetime(df_t['time'], unit='ms')
                df_t['usd'] = pd.to_numeric(df_t['px'], errors='coerce') * pd.to_numeric(df_t['sz'], errors='coerce')
                print(f"\n最近 {len(trades)} 筆交易")
                print(df_t[['time','coin','side','sz','px','usd']].head(8))
                header2 = not pd.io.common.file_exists(trade_file)
                df_t.to_csv(trade_file, mode='a', header=header2, index=False)
        except:
            pass  # 交易抓不到也不影響主程式

        print(f"\n存檔完成 → {pos_file}")
        print("="*100)

        time.sleep(45)

    except Exception as e:
        print(f"未知錯誤：{e}，30 秒後重試...")
        time.sleep(30)