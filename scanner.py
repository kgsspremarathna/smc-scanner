import streamlit as st
import pandas as pd
import requests
import pandas_ta_classic as ta
import time
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="STRYK: Auto Alert Scanner", layout="wide")
st.title("🎯 STRYK: Auto Alert Scanner (30m Refresh)")
st.markdown("Scanning ALL Binance Coins & Sending Alerts Automatically Every 30 Minutes")

# 🔥 Auto Refresh Setup (30 Minutes = 1800000 ms)
st_autorefresh(interval=1800000, limit=None, key="auto_refresh")

BINANCE_API = "https://fapi2.binance.com/fapi/v1"

@st.cache_data(ttl=300)
def get_all_futures_symbols():
    try:
        res = requests.get(f"{BINANCE_API}/exchangeInfo", timeout=15)
        data = res.json()
        symbols = [s['symbol'] for s in data['symbols'] if s['quoteAsset'] == 'USDT' and s['status'] == 'TRADING' and s['contractType'] == 'PERPETUAL']
        return symbols
    except: return []

def get_klines(symbol, interval, limit=200):
    try:
        url = f"{BINANCE_API}/klines?symbol={symbol}&interval={interval}&limit={limit}"
        res = requests.get(url, timeout=5)
        if res.status_code != 200: return None
        data = res.json()
        df = pd.DataFrame(data, columns=['time', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'taker_base', 'taker_quote', 'ignore'])
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        return df
    except: return None

# --- Check Functions ---
def check_trend(df):
    try:
        ema50 = ta.ema(df['close'], length=50).iloc[-1]
        ema200 = ta.ema(df['close'], length=200).iloc[-1]
        if pd.isna(ema200): return "FAIL"
        close = df['close'].iloc[-1]
        if (close > ema50 and ema50 > ema200) or (close < ema50 and ema50 < ema200): return "PASS"
        return "FAIL"
    except: return "FAIL"

def check_sweep(df):
    try:
        recent_high = df['high'].iloc[-22:-2].max()
        recent_low = df['low'].iloc[-22:-2].min()
        for _, row in df.iloc[-2:].iterrows():
            if (row['high'] > recent_high and row['close'] < recent_high) or (row['low'] < recent_low and row['close'] > recent_low): return "PASS"
        return "FAIL"
    except: return "FAIL"

def check_bos(df):
    try:
        recent_high = df['high'].iloc[-21:-1].max()
        recent_low = df['low'].iloc[-21:-1].min()
        if df['close'].iloc[-1] > recent_high or df['close'].iloc[-1] < recent_low: return "PASS"
        return "FAIL"
    except: return "FAIL"

def check_fvg(df):
    try:
        for i in range(len(df)-5, len(df)-1):
            if df['low'].iloc[i+2] > df['high'].iloc[i] or df['high'].iloc[i+2] < df['low'].iloc[i]: return "PASS"
        return "FAIL"
    except: return "FAIL"

def send_discord_alert(webhook_url, message):
    if not webhook_url: return
    data = {"content": message}
    try:
        requests.post(webhook_url, json=data)
    except: pass

# --- Main UI ---
st.sidebar.header("⚙️ Auto Scanner Settings")
webhook_url = st.sidebar.text_input("Discord Webhook URL", type="password")
st.sidebar.info("⏳ This scanner will auto-refresh every 30 minutes.")

# We use session_state to avoid running the scan on every page load
if "last_scan_time" not in st.session_state:
    st.session_state.last_scan_time = 0

current_time = time.time()

# Check if 30 minutes passed or if it's the first run
if current_time - st.session_state.last_scan_time > 1800 or st.session_state.last_scan_time == 0:
    with st.spinner("Fetching ALL Binance Futures Coins..."):
        symbols = get_all_futures_symbols()
        
    if not symbols:
        st.error("Binance API Blocked.")
        st.stop()
        
    timeframes = ["5m", "15m", "30m", "1h", "2h", "4h", "1d", "1w"]
    
    all_results = []
    total_scans = len(symbols) * len(timeframes)
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    scan_count = 0
    
    for symbol in symbols:
        for tf in timeframes:
            scan_count += 1
            status_text.text(f"Scanning {symbol} on {tf}... ({scan_count}/{total_scans})")
            
            df = get_klines(symbol, tf, limit=200)
            if df is None or len(df) < 200:
                progress_bar.progress(scan_count / total_scans)
                continue
                
            trend = check_trend(df)
            sweep = check_sweep(df)
            bos = check_bos(df)
            fvg = check_fvg(df)
            
            if trend == "PASS" and sweep == "PASS" and bos == "PASS" and fvg == "PASS":
                current_price = df['close'].iloc[-1]
                ema50 = ta.ema(df['close'], length=50).iloc[-1]
                direction = "🟢 BUY" if current_price > ema50 else "🔴 SELL"
                
                all_results.append({
                    "Coin": symbol,
                    "TF": tf,
                    "Direction": direction,
                    "Price": current_price
                })
                
                if webhook_url:
                    alert_msg = f"🚨 **STRYK MAIN 4 ALERT: {symbol}** 🚨\n" \
                                f"Timeframe: {tf}\n" \
                                f"Direction: {direction}\n" \
                                f"Current Price: {current_price}\n" \
                                f"Status: ✅ MAIN 4 PASS"
                    send_discord_alert(webhook_url, alert_msg)
            
            progress_bar.progress(scan_count / total_scans)
            time.sleep(0.05)

    st.session_state.last_scan_time = time.time()
    status_text.text("Scan Complete! ✅ Waiting for next 30m refresh...")
    
    if all_results:
        df_results = pd.DataFrame(all_results)
        st.subheader("🔥 All Main 4 Passed Setups (All Coins & TFs)")
        st.dataframe(df_results, use_container_width=True)
    else:
        st.warning("No Main 4 Setups found right now.")
else:
    st.info(f"⏳ Waiting for next scan. Last scan was {int((current_time - st.session_state.last_scan_time)/60)} minutes ago.")
