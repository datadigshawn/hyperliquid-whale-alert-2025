"""
🦈 Hyperliquid Whale Tracker v2
===================================
監控指定錢包：
  - Open orders（新掛單 / 取消 / 部分成交）
  - Positions（開倉 / 平倉 / 加減倉 / 反向）
  - 涵蓋 main perp dex + builder-deployed subdex（如 xyz）

環境變數（.env 自動載入）：
  TARGET_WALLET      監控錢包地址
  TELEGRAM_TOKEN     Telegram Bot Token
  TELEGRAM_CHAT_ID   推播目的地 chat_id
  PERP_DEXS          追蹤的 perp dex 列表（逗號分隔，預設: ,xyz。空字串 = main dex）
  POLL_SEC           輪詢間隔（預設 15 秒）
"""
from __future__ import annotations

import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# ── 自動載入 .env（同目錄） ────────────────────────────────
_ENV_FILE = Path(__file__).resolve().parent / ".env"
if _ENV_FILE.exists():
    for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

WALLET         = os.getenv("TARGET_WALLET", "0x9d32884370875f2960d5cc4b95be26687d69aff5")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
CHAT_ID        = os.getenv("TELEGRAM_CHAT_ID", "")
POLL_SEC       = int(os.getenv("POLL_SEC", "15"))
# 逗號分隔；空字串代表 main dex；e.g., "" 就是只看 main; ",xyz" 就是 main+xyz
PERP_DEXS      = [s.strip() for s in os.getenv("PERP_DEXS", ",xyz").split(",")]

API_URL = "https://api.hyperliquid.xyz/info"


# ── Utility ────────────────────────────────────────────
def fmt_time() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _short_wallet(w: str) -> str:
    return f"{w[:10]}...{w[-8:]}"


def _fmt_num(n: float, dp: int = 2) -> str:
    """簡潔數字格式化：$1,234.56 / $1.2M / $45.7K"""
    abs_n = abs(n)
    if abs_n >= 1_000_000:
        return f"${n/1_000_000:,.2f}M"
    if abs_n >= 1_000:
        return f"${n/1_000:,.1f}K"
    return f"${n:,.{dp}f}"


def send_telegram(msg: str) -> bool:
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print(f"⚠️ 推播失敗：缺少 TOKEN 或 CHAT_ID")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML",
               "disable_web_page_preview": True}
    try:
        r = requests.post(url, data=payload, timeout=10)
        if r.status_code == 200:
            print(f"📱 已推播：{msg[:60].replace(chr(10),' ')}...")
            return True
        print(f"推播失敗 {r.status_code}: {r.text[:200]}")
        return False
    except Exception as e:
        print(f"推播錯誤：{e}")
        return False


# ── Hyperliquid API 封裝 ────────────────────────────────
def api_post(body: dict, timeout: int = 15) -> dict | list | None:
    try:
        r = requests.post(API_URL, json=body, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"❌ API 錯誤 {body.get('type')}: {e}")
        return None


def fetch_positions(wallet: str, dex: str) -> dict:
    """回傳 {coin: position_dict}。dex="" 代表 main dex。"""
    body = {"type": "clearinghouseState", "user": wallet}
    if dex:
        body["dex"] = dex
    data = api_post(body)
    if not isinstance(data, dict):
        return {}
    positions = {}
    for ap in data.get("assetPositions", []):
        p = ap.get("position", {})
        coin = p.get("coin")
        if coin and float(p.get("szi", 0) or 0) != 0:
            positions[coin] = p
    return positions


def fetch_all_positions(wallet: str) -> dict:
    """跨所有 dex 合併持倉。回傳 {(dex, coin): position_dict}。"""
    result = {}
    for dex in PERP_DEXS:
        for coin, p in fetch_positions(wallet, dex).items():
            result[(dex or "main", coin)] = p
    return result


def fetch_open_orders(wallet: str) -> dict:
    """回傳 {oid: order_dict}。"""
    data = api_post({"type": "openOrders", "user": wallet})
    if not isinstance(data, list):
        return {}
    return {o["oid"]: o for o in data}


# ── 比對變化 ─────────────────────────────────────────────
def diff_positions(old: dict, new: dict) -> list:
    """比對兩個 positions dict，回傳事件列表。"""
    events = []
    for key in new.keys() | old.keys():
        old_p = old.get(key)
        new_p = new.get(key)
        dex, coin = key
        if new_p and not old_p:
            # 新開倉
            szi = float(new_p.get("szi", 0))
            entry = float(new_p.get("entryPx", 0))
            lev = new_p.get("leverage", {}).get("value", 1)
            side = "多" if szi > 0 else "空"
            events.append({
                "kind": "position_open", "dex": dex, "coin": coin,
                "side": side, "size": abs(szi), "entry": entry, "lev": lev,
                "position_value": float(new_p.get("positionValue", 0)),
            })
        elif old_p and not new_p:
            # 平倉
            old_szi = float(old_p.get("szi", 0))
            old_entry = float(old_p.get("entryPx", 0))
            side = "多" if old_szi > 0 else "空"
            events.append({
                "kind": "position_close", "dex": dex, "coin": coin,
                "side": side, "size": abs(old_szi), "entry": old_entry,
            })
        elif new_p and old_p:
            old_szi = float(old_p.get("szi", 0))
            new_szi = float(new_p.get("szi", 0))
            if old_szi * new_szi < 0:
                # 反向（多翻空或空翻多）
                events.append({
                    "kind": "position_flip", "dex": dex, "coin": coin,
                    "old_szi": old_szi, "new_szi": new_szi,
                    "entry": float(new_p.get("entryPx", 0)),
                })
            elif abs(abs(new_szi) - abs(old_szi)) >= 1:
                # 加倉或減倉
                delta = abs(new_szi) - abs(old_szi)
                events.append({
                    "kind": "position_change", "dex": dex, "coin": coin,
                    "old_size": abs(old_szi), "new_size": abs(new_szi),
                    "delta": delta,
                    "side": "多" if new_szi > 0 else "空",
                    "entry": float(new_p.get("entryPx", 0)),
                })
    return events


def diff_orders(old: dict, new: dict) -> list:
    events = []
    for oid in new.keys() | old.keys():
        old_o = old.get(oid)
        new_o = new.get(oid)
        if new_o and not old_o:
            events.append({"kind": "order_new", "order": new_o})
        elif old_o and not new_o:
            events.append({"kind": "order_gone", "order": old_o})
        elif new_o and old_o:
            d = abs(float(old_o["sz"]) - float(new_o["sz"]))
            if d > 1:
                events.append({"kind": "order_partial",
                               "old_sz": float(old_o["sz"]),
                               "new_sz": float(new_o["sz"]),
                               "order": new_o})
    return events


# ── 訊息格式 ────────────────────────────────────────────
def fmt_position_line(dex: str, coin: str, p: dict) -> str:
    szi = float(p.get("szi", 0))
    side = "🔴 SHORT" if szi < 0 else "🟢 LONG"
    entry = float(p.get("entryPx", 0))
    value = float(p.get("positionValue", 0))
    pnl = float(p.get("unrealizedPnl", 0))
    lev = p.get("leverage", {}).get("value", 1)
    lev_type = p.get("leverage", {}).get("type", "cross")
    dex_tag = f"[{dex}] " if dex != "main" else ""
    pnl_str = f"+{_fmt_num(pnl)}" if pnl >= 0 else f"-{_fmt_num(abs(pnl))}"
    return (
        f"{dex_tag}<b>{coin}</b> {side} {lev}x ({lev_type})\n"
        f"  數量: <b>{abs(szi):,.0f}</b>  入場: <b>${entry:,.4f}</b>\n"
        f"  倉位價值: {_fmt_num(value)}  未實現盈虧: <b>{pnl_str}</b>"
    )


def fmt_position_open(e: dict) -> str:
    dex_tag = f"[{e['dex']}] " if e["dex"] != "main" else ""
    side_emoji = "🟢" if e["side"] == "多" else "🔴"
    return (
        f"{side_emoji} <b>新開倉！</b>\n\n"
        f"{dex_tag}<b>{e['coin']}</b> {e['side']}單 {e['lev']}x\n"
        f"數量: <b>{e['size']:,.0f}</b>\n"
        f"入場價: <b>${e['entry']:,.4f}</b>\n"
        f"倉位價值: {_fmt_num(e['position_value'])}\n"
        f"時間: {fmt_time()}"
    )


def fmt_position_close(e: dict) -> str:
    dex_tag = f"[{e['dex']}] " if e["dex"] != "main" else ""
    return (
        f"⚪ <b>平倉完成！</b>\n\n"
        f"{dex_tag}<b>{e['coin']}</b> {e['side']}單\n"
        f"原數量: <b>{e['size']:,.0f}</b>\n"
        f"原入場價: ${e['entry']:,.4f}\n"
        f"時間: {fmt_time()}"
    )


def fmt_position_change(e: dict) -> str:
    dex_tag = f"[{e['dex']}] " if e["dex"] != "main" else ""
    verb = "加倉" if e["delta"] > 0 else "減倉"
    emoji = "➕" if e["delta"] > 0 else "➖"
    return (
        f"{emoji} <b>{verb}！</b>\n\n"
        f"{dex_tag}<b>{e['coin']}</b> {e['side']}單\n"
        f"數量: <b>{e['old_size']:,.0f}</b> → <b>{e['new_size']:,.0f}</b>  ({'+' if e['delta']>0 else ''}{e['delta']:,.0f})\n"
        f"當前均價: ${e['entry']:,.4f}\n"
        f"時間: {fmt_time()}"
    )


def fmt_position_flip(e: dict) -> str:
    dex_tag = f"[{e['dex']}] " if e["dex"] != "main" else ""
    old_side = "多" if e["old_szi"] > 0 else "空"
    new_side = "多" if e["new_szi"] > 0 else "空"
    return (
        f"🔄 <b>方向反轉！</b>\n\n"
        f"{dex_tag}<b>{e['coin']}</b>: {old_side}單 → <b>{new_side}單</b>\n"
        f"新數量: <b>{abs(e['new_szi']):,.0f}</b>\n"
        f"新入場: ${e['entry']:,.4f}\n"
        f"時間: {fmt_time()}"
    )


def fmt_order_new(o: dict) -> str:
    sz = float(o["sz"])
    px = float(o["limitPx"])
    side = "買單" if o["side"] == "B" else "賣單"
    coin = o.get("coin", "?")
    return (
        f"🟥 <b>新掛單！</b>\n\n"
        f"<b>{coin}</b> {side}\n"
        f"數量: <b>{sz:,.0f}</b>  價格: <b>${px:,.4f}</b>\n"
        f"時間: {fmt_time()}"
    )


def fmt_order_gone(o: dict) -> str:
    sz = float(o["sz"])
    px = float(o["limitPx"])
    side = "買單" if o["side"] == "B" else "賣單"
    coin = o.get("coin", "?")
    return (
        f"🟩 <b>訂單消失！</b>\n\n"
        f"<b>{coin}</b> {side}\n"
        f"數量: <b>{sz:,.0f}</b>  價格: ${px:,.4f}\n"
        f"狀態: 成交或取消\n"
        f"時間: {fmt_time()}"
    )


def fmt_order_partial(e: dict) -> str:
    o = e["order"]
    px = float(o["limitPx"])
    side = "買單" if o["side"] == "B" else "賣單"
    coin = o.get("coin", "?")
    return (
        f"🟨 <b>部分成交！</b>\n\n"
        f"<b>{coin}</b> {side}\n"
        f"價格: ${px:,.4f}\n"
        f"數量: <b>{e['old_sz']:,.0f}</b> → <b>{e['new_sz']:,.0f}</b>\n"
        f"成交: <b>{abs(e['old_sz']-e['new_sz']):,.0f}</b>\n"
        f"時間: {fmt_time()}"
    )


# ── 主流程 ──────────────────────────────────────────────
total_alerts = 0


def signal_handler(sig, frame):
    send_telegram(
        f"🛑 <b>監控服務已停止</b>\n\n"
        f"⏰ 停止時間: {fmt_time()}\n"
        f"📈 總共推播: <b>{total_alerts}</b> 則訊息"
    )
    print("\n👋 監控已停止")
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def send_startup_snapshot():
    """啟動時發送當前持倉快照。"""
    positions = fetch_all_positions(WALLET)
    orders    = fetch_open_orders(WALLET)

    lines = [
        f"🦈 <b>鯨魚雷達已啟動！</b>",
        f"📍 地址: <code>{_short_wallet(WALLET)}</code>",
        f"⏱ 頻率: 每 {POLL_SEC} 秒",
        f"🌐 Dex: main{''.join(f'+{d}' for d in PERP_DEXS if d)}",
        f"⏰ {fmt_time()}",
        "",
    ]

    if positions:
        lines.append(f"📊 <b>當前持倉 ({len(positions)})</b>")
        # 總 PnL
        total_pnl = sum(float(p.get("unrealizedPnl", 0)) for p in positions.values())
        total_val = sum(float(p.get("positionValue", 0)) for p in positions.values())
        lines.append(f"💰 倉位總值: {_fmt_num(total_val)}  未實現: {'+' if total_pnl>=0 else '-'}{_fmt_num(abs(total_pnl))}")
        lines.append("")
        for (dex, coin), p in positions.items():
            lines.append(fmt_position_line(dex, coin, p))
            lines.append("")
    else:
        lines.append("📊 <b>當前無持倉</b>")
        lines.append("")

    if orders:
        lines.append(f"📋 <b>當前掛單: {len(orders)}</b>")
    else:
        lines.append("📋 <b>當前無掛單</b>")

    send_telegram("\n".join(lines))
    return positions, orders


def main():
    print(f"✅ 監控啟動 | 錢包: {WALLET}")
    print(f"   dex: {PERP_DEXS} | 頻率: {POLL_SEC}s")

    last_positions, last_orders = send_startup_snapshot()
    last_heartbeat = time.time()
    global total_alerts

    while True:
        try:
            # 1. Positions 變化
            new_positions = fetch_all_positions(WALLET)
            pos_events = diff_positions(last_positions, new_positions)
            for e in pos_events:
                kind = e["kind"]
                if kind == "position_open":
                    send_telegram(fmt_position_open(e))
                elif kind == "position_close":
                    send_telegram(fmt_position_close(e))
                elif kind == "position_change":
                    send_telegram(fmt_position_change(e))
                elif kind == "position_flip":
                    send_telegram(fmt_position_flip(e))
                total_alerts += 1

            # 2. Orders 變化
            new_orders = fetch_open_orders(WALLET)
            order_events = diff_orders(last_orders, new_orders)
            for e in order_events:
                kind = e["kind"]
                if kind == "order_new":
                    send_telegram(fmt_order_new(e["order"]))
                elif kind == "order_gone":
                    send_telegram(fmt_order_gone(e["order"]))
                elif kind == "order_partial":
                    send_telegram(fmt_order_partial(e))
                total_alerts += 1

            total_events = len(pos_events) + len(order_events)
            if total_events:
                print(f"{fmt_time()} | 偵測 {total_events} 個事件（positions={len(pos_events)} orders={len(order_events)}）")

            # 3. 心跳（每小時）
            if time.time() - last_heartbeat > 3600:
                total_pnl = sum(float(p.get("unrealizedPnl", 0)) for p in new_positions.values())
                total_val = sum(float(p.get("positionValue", 0)) for p in new_positions.values())
                send_telegram(
                    f"💚 <b>系統運行正常</b>\n\n"
                    f"⏰ {fmt_time()}\n"
                    f"📊 持倉: <b>{len(new_positions)}</b> 個  掛單: <b>{len(new_orders)}</b>\n"
                    f"💰 倉位總值: {_fmt_num(total_val)}\n"
                    f"📈 未實現盈虧: {'+' if total_pnl>=0 else '-'}{_fmt_num(abs(total_pnl))}\n"
                    f"📢 累計推播: <b>{total_alerts}</b>"
                )
                last_heartbeat = time.time()

            last_positions = new_positions
            last_orders    = new_orders
            time.sleep(POLL_SEC)

        except Exception as e:
            send_telegram(f"⚠️ <b>監控錯誤</b>\n\n<code>{str(e)[:300]}</code>\n{fmt_time()}")
            print(f"❌ 錯誤：{e}")
            time.sleep(30)


if __name__ == "__main__":
    main()
