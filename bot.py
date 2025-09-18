# pro_scalper_pro.py
import os
import time
import requests
import pandas as pd
from datetime import datetime
import pytz

# ================= CONFIG =================
TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
CHAT_ID = "YOUR_CHAT_ID"

SYMBOLS = ["BTCUSDT","ETHUSDT","BNBUSDT","XRPUSDT","ADAUSDT"]
INTERVAL = "1m"
CANDLES = 100
CHECK_INTERVAL = 15  # seconds between symbol scans
ACCOUNT_BALANCE_USDT = 1000
RISK_PER_TRADE_PERCENT = 1.0
PRO_SL_PERCENT = 0.8
PRO_TP_PERCENT = 2.7

HEADERS = {"User-Agent": "pro_scalper_bot/1.0"}
last_alerts = {}
timezone_pk = pytz.timezone("Asia/Karachi")

# ================= HELPERS =================
def get_klines(symbol, interval="1m", limit=100):
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    try:
        r = requests.get(url, params=params, timeout=10, headers=HEADERS)
        r.raise_for_status()
        data = r.json()
        df = pd.DataFrame(data, columns=[
            "open_time","open","high","low","close","volume",
            "close_time","quote_vol","num_trades","taker_base",
            "taker_quote","ignore"
        ])
        for col in ["open","high","low","close","volume"]:
            df[col] = pd.to_numeric(df[col])
        return df
    except Exception as e:
        print(f"[get_klines] {symbol} error:", e)
        return None

def ema(series, length):
    return series.ewm(span=length, adjust=False).mean()

def rsi(series, length=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    ma_up = up.ewm(alpha=1/length, adjust=False).mean()
    ma_down = down.ewm(alpha=1/length, adjust=False).mean()
    rs = ma_up/(ma_down + 1e-9)
    return 100-(100/(1+rs))

def detect_structure(df):
    """Check last 5 candles for bullish or bearish swing"""
    if len(df) < 6: return "neutral"
    highs = df['high'].tail(6)
    lows = df['low'].tail(6)
    if all(highs[i] > highs[i-1] and lows[i] > lows[i-1] for i in range(1,6)):
        return "bull"
    elif all(highs[i] < highs[i-1] and lows[i] < lows[i-1] for i in range(1,6)):
        return "bear"
    return "neutral"

def calculate_signal(df):
    price = df['close'].iloc[-1]
    ema9 = ema(df['close'], 9).iloc[-1]
    ema21 = ema(df['close'], 21).iloc[-1]
    rsi14 = rsi(df['close'], 14).iloc[-1]
    structure = detect_structure(df)

    signal = None
    if structure == "bull" and ema9 > ema21 and rsi14 < 40:
        signal = "BUY"
    elif structure == "bear" and ema9 < ema21 and rsi14 > 60:
        signal = "SELL"
    return signal, price

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode":"HTML"}
    try:
        requests.post(url, json=payload, timeout=8)
    except: pass

def format_alert(symbol, action, price):
    sl = price * (1 - PRO_SL_PERCENT/100) if action=="BUY" else price * (1 + PRO_SL_PERCENT/100)
    tp = price * (1 + PRO_TP_PERCENT/100) if action=="BUY" else price * (1 - PRO_TP_PERCENT/100)
    return f"🚀 <b>{symbol}</b> {action} SIGNAL\n💰 Entry: {price:.2f} USDT\n🛑 SL: {sl:.2f}\n🎯 TP: {tp:.2f}\n📊 Risk/Reward ~ 1:{PRO_TP_PERCENT/PRO_SL_PERCENT:.1f}"

# ================= MAIN LOOP =================
def main():
    print("🔥 Pro Scalper Bot Started...")
    while True:
        for sym in SYMBOLS:
            try:
                df = get_klines(sym, INTERVAL, CANDLES)
                if df is None: continue
                action, price = calculate_signal(df)
                if action:
                    key = f"{sym}_{action}"
                    minute_key = datetime.now(timezone_pk).strftime("%Y-%m-%d %H:%M")
                    if last_alerts.get(key) != minute_key:
                        last_alerts[key] = minute_key
                        msg = format_alert(sym, action, price)
                        send_telegram(msg)
                        print(f"[ALERT] {sym} {action} @ {price}")
            except Exception as e:
                print(f"[MAIN] {sym} error:", e)
            time.sleep(1)
        time.sleep(CHECK_INTERVAL)

if __name__=="__main__":
    main()
