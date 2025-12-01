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
        
        # Pola Candle
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

# --- SMART SCANNER V5 (90% PROBABILITY FILTER) ---
def scan_dynamic_market():
    try:
        exc = get_exchange()
        tickers = exc.fetch_tickers()
    except: return []

    # Ambil 75 Koin Volume Terbesar (Likuiditas Tinggi = Chart Lebih Valid)
    valid_symbols = [s for s, d in tickers.items() if s.endswith('/USDT')]
    candidates = sorted(valid_symbols, key=lambda x: tickers[x].get('quoteVolume', 0), reverse=True)[:75]
    
    scored_candidates = []
    
    for sym in candidates:
        # Gunakan limit 250 agar scanner cepat tapi data indikator tetap ada
        df = fetch_market_data(sym, '1h', limit=250)
        df = calc_technical_indicators(df)
        if df is None or 'RSI' not in df.columns: continue
        
        poc = calc_volume_profile(df)
        last = df.iloc[-1]
        
        # --- ALGORITMA SCORING V5 ---
        score = 0
        bias = "NEUTRAL"
        
        # 1. Trend Alignment (Follow The Trend)
        if last['close'] > last.get('EMA_200', 0): score += 3 # Bobot besar
        else: score -= 3
        
        # 2. Volume Profile (Support/Resist Valid)
        if last['close'] > poc: score += 2
        else: score -= 2
        
        # 3. Momentum (RSI) - Penentu Entry
        rsi = last.get('RSI', 50)
        if rsi < 30: 
            score += 6 # Oversold Ekstrem (Potensi Bounce Tinggi)
            bias = "LONG (Sniper Bounce)"
        elif rsi > 70: 
            score -= 6 # Overbought Ekstrem (Potensi Dump Tinggi)
            bias = "SHORT (Sniper Pullback)"
            
        # 4. Pola Candle (Konfirmasi Instan)
        if last['Is_Bull_Engulf']: score += 2
        if last['Is_Bear_Engulf']: score -= 2
        
        # Tentukan Bias jika bukan Reversal Ekstrem
        if "Sniper" not in bias:
            if score > 3: bias = "LONG (Strong Trend)"
            elif score < -3: bias = "SHORT (Strong Trend)"
            
        # Filter: Hanya masukkan jika Volume hidup dan Skor Signifikan
        if last['volume'] > (last.get('Vol_SMA', 0) * 0.4) and abs(score) >= 4:
            scored_candidates.append({'symbol': sym, 'bias': bias, 'score': abs(score), 'poc': poc})
            
    # Kembalikan 3 Koin dengan Skor Teknikal Tertinggi (Paling Valid)
    return sorted(scored_candidates, key=lambda x: x['score'], reverse=True)[:3]

# --- AI CONTEXT GENERATOR (V5 - FULL DATA PACK) ---
def get_ai_context_indo(symbol, poc_val=0):
    # 1. Data Chart
    df_chart = fetch_market_data(symbol, '1h', limit=1000)
    df_trend = fetch_market_data(symbol, '1d', limit=1000)
    
    if df_chart is None: return None, "Error", 0, {}
    
    df_chart = calc_technical_indicators(df_chart)
    df_trend = calc_technical_indicators(df_trend)
    if poc_val == 0: poc_val = calc_volume_profile(df_chart)
        
    l_1h = df_chart.iloc[-1]
    l_1d = df_trend.iloc[-1]
    
    # 2. Data Eksternal
    btc_trend = get_btc_trend()
    oi = fetch_open_interest(symbol)
    fund_data = get_fundamental_data(symbol)
    news_data = get_crypto_news(symbol)
    sent_score = analyze_sentiment_score(news_data)
    
    # 3. Pola Candle
    patt = []
    if l_1h['Is_Hammer']: patt.append("Hammer")
    if l_1h['Is_Bull_Engulf']: patt.append("Bullish Engulfing")
    if l_1h['Is_Bear_Engulf']: patt.append("Bearish Engulfing")
    candle_txt = ", ".join(patt) if patt else "Tidak ada pola signifikan"
    
    adaptive_rules = get_adaptive_rules()
    
    # 4. Context Builder
    context = f"""
    [ATURAN BELAJAR]: {adaptive_rules if adaptive_rules else "Analisa normal."}
    [MARKET UTAMA]: BTC Trend (H4): {btc_trend}
    [DATA TEKNIKAL {symbol}]:
    - Harga: {l_1h['close']}
    - POC: {poc_val:.4f}
    - RSI H1: {l_1h['RSI']:.2f}
    - Trend D1: {'BULLISH' if l_1d['close'] > l_1d['EMA_200'] else 'BEARISH'}
    - Open Interest: {oi}
    - Pola Candle: {candle_txt}
    - Support/Resist: {l_1h['Sup']} / {l_1h['Res']}
    
    [FUNDAMENTAL & BERITA]:
    {fund_data}
    
    [NEWS SENTIMENT]:
    Score: {sent_score}
    Headlines: {news_data}
    """
    
    extra_data = {'btc_trend': btc_trend, 'sentiment': sent_score, 'news': news_data}
    
    # RETURN 4 DATA (FIX CRASH)
    return df_chart, context, poc_val, extra_data