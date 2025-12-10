import requests
import pandas as pd
import time
from datetime import datetime

# 你的 API Key
API_KEY = "YOUR_Cfae3c13a8b5440c78234b9e028141318"  # 記得替換！
BASE_URL = "https://open-api-v4.coinglass.com"
WALLET_ADDRESS = "0xb317d2bc2d3d2df5fa441b5bae0ab9d8b07283ae"  # 目標錢包地址

headers = {
    "CG-API-KEY": API_KEY,
    "accept": "application/json"
}

def track_hyperliquid_whales(page=1, page_size=100):
    """追蹤 Hyperliquid 鯨魚持倉（檢查是否包含目標地址）"""
    url = f"{BASE_URL}/api/hyperliquid/whale-position"
    params = {
        "page": page,
        "pageSize": page_size  # 每頁筆數，預設 100
    }
    
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()
        if data.get("code") == "0":
            positions = data.get("data", {}).get("list", [])
            df = pd.DataFrame(positions)
            if not df.empty:
                df['track_time'] = datetime.now().isoformat()
                # 檢查目標地址
                matching = df[df['user'].str.lower() == WALLET_ADDRESS.lower()]
                if not matching.empty:
                    print(f"✅ 找到目標地址 {WALLET_ADDRESS} 的持倉！")
                    print(matching[['user', 'symbol', 'position_size', 'entry_price', 'mark_price', 'unrealized_pnl', 'track_time']])
                else:
                    print(f"❌ 未找到 {WALLET_ADDRESS} 在鯨魚持倉中（可能持倉 < $1M）")
                print(f"總鯨魚持倉 ({len(df)} 筆):")
                print(df[['user', 'symbol', 'position_size', 'entry_price', 'mark_price', 'unrealized_pnl']].head())
                return df
        else:
            print(f"API 回應錯誤: {data.get('msg', 'Unknown')}")
    else:
        print(f"HTTP 錯誤: {response.status_code} - {response.text}")
    return None

# 主程式：每 5 分鐘追蹤一次，存到 CSV
csv_file = "hyperliquid_whale_tracking.csv"
print("開始追蹤 Hyperliquid 鯨魚持倉（檢查目標地址）...")

# 跑 10 次示例（改成 while True: 無限監測）
for i in range(10):
    print(f"\n--- 輪次 {i+1} - {datetime.now()} ---")
    
    df = track_hyperliquid_whales()
    if df is not None:
        # 追加到 CSV（第一次寫 header）
        df.to_csv(csv_file, mode='a', header=not pd.io.common.file_exists(csv_file), index=False)
        print(f"數據已存到 {csv_file}")
    
    print("等待 5 分鐘...")
    time.sleep(300)  # 300 秒 = 5 分鐘