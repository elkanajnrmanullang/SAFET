import ccxt
import pandas as pd
import pandas_ta as ta
import numpy as np
from backend.database import get_adaptive_rules

# --- INTEGRASI MODUL EKSTERNAL ---
try:
    from backend.fundamental import get_fundamental_data
    from backend.news import get_crypto_news, analyze_sentiment_score
except ImportError:
    def get_fundamental_data(s): return "Data Fundamental tidak tersedia."
    def get_crypto_news(s): return "Berita tidak tersedia."
    def analyze_sentiment_score(t): return "NEUTRAL"

# --- KONEKSI ---
def get_exchange():
    return ccxt.binance({'enableRateLimit': True, 'timeout': 30000, 'options': {'defaultType': 'future'}})

# --- MARKET DATA ---
def get_market_overview():
    try:
        exc = get_exchange()
        btc = exc.fetch_ticker('BTC/USDT')
        eth = exc.fetch_ticker('ETH/USDT')
        return {
            'btc_price': btc['last'], 'btc_change': btc['percentage'],
            'eth_price': eth['last'], 'eth_change': eth['percentage']
        }
    except:
        return {'btc_price': 0, 'btc_change': 0, 'eth_price': 0, 'eth_change': 0}

def fetch_open_interest(symbol):
    try:
        exc = get_exchange()
        oi = exc.fetch_open_interest(symbol)
        return oi.get('openInterestAmount', 0)
    except: return 0

def get_btc_trend():
    try:
        df = fetch_market_data('BTC/USDT', '4h', limit=200)
        if df is None: return "UNKNOWN"
        df['EMA_50'] = df.ta.ema(length=50)
        return "BULLISH" if df.iloc[-1]['close'] > df.iloc[-1]['EMA_50'] else "BEARISH"
    except: return "UNKNOWN"

# --- CORE CALCULATIONS ---
def calc_volume_profile(df, bins=100): 
    try:
        price_min, price_max = df['low'].min(), df['high'].max()
        price_range = np.linspace(price_min, price_max, bins)
        vp = np.zeros(bins - 1)
        for i in range(len(df)):
            idx = np.digitize(df['close'].iloc[i], price_range) - 1
            if 0 <= idx < len(vp): vp[idx] += df['volume'].iloc[i]
        max_idx = np.argmax(vp)
        return (price_range[max_idx] + price_range[max_idx+1]) / 2
    except: return df['close'].iloc[-1]

def get_fibonacci_levels(df, period=300):
    """
    Fibonacci Retracement (High/Low 300 candle terakhir ~ 12 Hari)
    """
    try:
        relevant = df.tail(period)
        high, low = relevant['high'].max(), relevant['low'].min()
        diff = high - low
        return {
            "Low": low, "High": high,
            "0.236": low + diff * 0.236,
            "0.382": low + diff * 0.382,
            "0.5": low + diff * 0.5,
            "0.618 (Golden)": low + diff * 0.618
        }
    except: return {}

def fetch_market_data(symbol, timeframe='1h', limit=1000): 
    try:
        exc = get_exchange()
        exc.ssl = False; exc.verify = False
        bars = exc.fetch_ohlcv(symbol, timeframe, limit=limit)
        if not bars: return None
        df = pd.DataFrame(bars, columns=['timestamp','open','high','low','close','volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except: return None

def calc_technical_indicators(df):
    if df is None or df.empty: return None
    try:
        df['EMA_50'] = df.ta.ema(length=50)
        df['EMA_200'] = df.ta.ema(length=200)
        df['RSI'] = df.ta.rsi(length=14)
        df['Vol_SMA'] = df['volume'].rolling(20).mean()
        df['ATR'] = df.ta.atr(length=14)
        
        # Stochastic RSI
        stoch = df.ta.stochrsi(length=14, rsi_length=14, k=3, d=3)
        if stoch is not None:
            df = pd.concat([df, stoch], axis=1)
            cols = stoch.columns
            df['Stoch_K'] = df[cols[0]]
            df['Stoch_D'] = df[cols[1]]
        else:
            df['Stoch_K'], df['Stoch_D'] = 50, 50
        
        # Candle Patterns
        o, c, h, l = df['open'], df['close'], df['high'], df['low']
        body = abs(c - o)
        df['Is_Hammer'] = ((pd.concat([o, c], axis=1).min(axis=1) - l) > (body * 2)) & ((h - pd.concat([o, c], axis=1).max(axis=1)) < body)
        prev_c, prev_o = c.shift(1), o.shift(1)
        df['Is_Bull_Engulf'] = (c > o) & (prev_c < prev_o) & (c > prev_o) & (o < prev_c)
        df['Is_Bear_Engulf'] = (c < o) & (prev_c > prev_o) & (c < prev_o) & (o > prev_c)
        df['Sup'] = df['low'].rolling(50).min()
        df['Res'] = df['high'].rolling(50).max()
        return df
    except: return df

# --- SCANNER FAIL-SAFE (PASTI ADA HASIL) ---
def scan_dynamic_market():
    try:
        exc = get_exchange()
        tickers = exc.fetch_tickers()
    except: return []

    valid_symbols = [s for s, d in tickers.items() if s.endswith('/USDT')]
    # Ambil 75 Koin Volume Terbesar
    candidates = sorted(valid_symbols, key=lambda x: tickers[x].get('quoteVolume', 0), reverse=True)[:75]
    
    hq_list = [] # High Quality (Skor >= 4)
    backup_list = [] # Backup (Volume hidup)
    
    for sym in candidates:
        df = fetch_market_data(sym, '1h', limit=250)
        df = calc_technical_indicators(df)
        if df is None or 'RSI' not in df.columns: continue
        
        poc = calc_volume_profile(df)
        last = df.iloc[-1]
        
        score = 0
        bias = "NEUTRAL"
        
        # Scoring Logic
        if last['close'] > last.get('EMA_200', 0): score += 3
        else: score -= 3
        
        if last['close'] > poc: score += 2
        else: score -= 2
        
        rsi = last.get('RSI', 50)
        stoch_k = last.get('Stoch_K', 50)
        
        # Momentum Sniper
        if rsi < 35 and stoch_k < 20: 
            score += 7; bias = "LONG (Sniper Bounce)"
        elif rsi > 65 and stoch_k > 80: 
            score -= 7; bias = "SHORT (Sniper Pullback)"
            
        if "Sniper" not in bias:
            if score > 3: bias = "LONG (Trend)"
            elif score < -3: bias = "SHORT (Trend)"
            
        item = {'symbol': sym, 'bias': bias, 'score': abs(score), 'poc': poc}
        
        # Fail-Safe Filter
        if last['volume'] > (last.get('Vol_SMA', 0) * 0.3):
            backup_list.append(item)
            if abs(score) >= 4: hq_list.append(item)
            
    # Priority Return
    if hq_list: return sorted(hq_list, key=lambda x: x['score'], reverse=True)[:3]
    return sorted(backup_list, key=lambda x: x['score'], reverse=True)[:3]

# --- AI CONTEXT (UPGRADED VISION) ---
def get_ai_context_indo(symbol, poc_val=0):
    # Fetch Data (1000 Candle untuk Indikator Presisi)
    df_chart = fetch_market_data(symbol, '1h', limit=1000)
    df_trend = fetch_market_data(symbol, '1d', limit=1000)
    
    if df_chart is None: return None, "Error", 0, {}
    
    df_chart = calc_technical_indicators(df_chart)
    df_trend = calc_technical_indicators(df_trend)
    if poc_val == 0: poc_val = calc_volume_profile(df_chart)
        
    l_1h = df_chart.iloc[-1]
    l_1d = df_trend.iloc[-1]
    
    # Hitung Fibonacci & Indikator Lain
    fibs = get_fibonacci_levels(df_chart)
    fib_txt = ", ".join([f"{k}: {v:.2f}" for k, v in fibs.items()])
    
    btc_trend = get_btc_trend()
    oi = fetch_open_interest(symbol)
    fund_data = get_fundamental_data(symbol)
    news_data = get_crypto_news(symbol)
    sent_score = analyze_sentiment_score(news_data)
    
    patt = []
    if l_1h['Is_Hammer']: patt.append("Hammer")
    if l_1h['Is_Bull_Engulf']: patt.append("Bullish Engulfing")
    if l_1h['Is_Bear_Engulf']: patt.append("Bearish Engulfing")
    candle_txt = ", ".join(patt) if patt else "Tidak ada"
    
    adaptive_rules = get_adaptive_rules()
    
    # --- BAGIAN KUNCI: EXPANDED VISION (24 Candle) ---
    chart_data = df_chart.tail(24)[['open','high','low','close']].values.tolist()
    
    context = f"""
    [SOP ANALISA USER (WAJIB IKUTI ALUR INI)]:
    1. ANALISA MULTITIMEFRAME: Cek Trend Besar (D1/BTC) -> Breakdown ke H1.
    2. VALIDASI STRUKTUR: Cek Support/Resist (POC, Fib), Indikator (RSI, Stoch).
    3. KONFIRMASI POLA: Cek Chart Pattern (dari data 24 jam) & Candle Pattern.
    
    [1. BIG PICTURE (TREND MAYOR)]:
    - BTC Trend (H4): {btc_trend}
    - Trend D1 {symbol}: {'BULLISH' if l_1d['close'] > l_1d['EMA_200'] else 'BEARISH'} (Harga: {l_1d['close']} vs EMA200: {l_1d['EMA_200']:.2f})
    
    [2. BREAKDOWN H1 (STRUCTURE & MOMENTUM)]:
    - Harga Saat Ini: {l_1h['close']}
    - POC (Volume Profile Trend Mayor): {poc_val:.4f}
    - Fibonacci Levels: {fib_txt}
    - RSI (14): {l_1h['RSI']:.2f}
    - Stochastic (K/D): {l_1h['Stoch_K']:.2f} / {l_1h['Stoch_D']:.2f}
    - Open Interest: {oi}
    
    [3. KONFIRMASI (PATTERN & CANDLE)]:
    - Pola Candle Terakhir: {candle_txt}
    - Support Terdekat: {l_1h['Sup']}
    - Resistance Terdekat: {l_1h['Res']}
    
    [DATA EKSTERNAL]:
    - Fundamental: {fund_data}
    - Sentiment Berita: {sent_score} ({news_data})
    
    [DATA CHART 24 JAM TERAKHIR (OHLC) - UNTUK ANALISA CHART PATTERN]:
    {chart_data}
    """
    
    extra_data = {'btc_trend': btc_trend, 'sentiment': sent_score, 'news': news_data}
    
    return df_chart, context, poc_val, extra_data