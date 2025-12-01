import ccxt
import pandas as pd
import pandas_ta as ta
import numpy as np
from backend.database import get_adaptive_rules

# --- KONEKSI GLOBAL ---
def get_exchange():
    # Timeout 30 detik untuk akomodasi kalkulasi berat & VPN
    return ccxt.binance({'enableRateLimit': True, 'timeout': 30000, 'options': {'defaultType': 'future'}})

# --- [FIXED] MARKET OVERVIEW FOR DASHBOARD ---
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
        # Return 0 jika gagal koneksi
        return {'btc_price': 0, 'btc_change': 0, 'eth_price': 0, 'eth_change': 0}

# --- CALCULATE VOLUME PROFILE (FRVP - Point of Control) ---
def calc_volume_profile(df, bins=100): # Bins ditingkatkan ke 100 untuk presisi
    try:
        price_min = df['low'].min()
        price_max = df['high'].max()
        price_range = np.linspace(price_min, price_max, bins)
        volume_profile = np.zeros(bins - 1)
        
        for i in range(len(df)):
            close_price = df['close'].iloc[i]
            vol = df['volume'].iloc[i]
            bin_idx = np.digitize(close_price, price_range) - 1
            if 0 <= bin_idx < len(volume_profile):
                volume_profile[bin_idx] += vol
        
        max_vol_idx = np.argmax(volume_profile)
        poc_price = (price_range[max_vol_idx] + price_range[max_vol_idx+1]) / 2
        return poc_price
    except:
        return df['close'].iloc[-1]

# --- FETCH DATA (PRECISION UPGRADE) ---
def fetch_market_data(symbol, timeframe='1h', limit=1000): 
    # Limit default dinaikkan ke 1000 agar EMA 200 & RSI akurat (TradingView standard)
    try:
        exc = get_exchange()
        exc.ssl = False; exc.verify = False
        bars = exc.fetch_ohlcv(symbol, timeframe, limit=limit)
        if not bars: return None
        df = pd.DataFrame(bars, columns=['timestamp','open','high','low','close','volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except: return None

# --- INDIKATOR LENGKAP ---
def calc_technical_indicators(df):
    if df is None or df.empty: return None
    try:
        # Trend
        df['EMA_50'] = df.ta.ema(length=50)
        df['EMA_200'] = df.ta.ema(length=200)
        # Momentum
        df['RSI'] = df.ta.rsi(length=14)
        # Volume Moving Average
        df['Vol_SMA'] = df['volume'].rolling(20).mean()
        # Volatility
        df['ATR'] = df.ta.atr(length=14)
        
        # Candle Patterns Logic
        o = df['open']; c = df['close']; h = df['high']; l = df['low']
        body = abs(c - o)
        
        # Hammer & Engulfing
        df['Is_Hammer'] = ((pd.concat([o, c], axis=1).min(axis=1) - l) > (body * 2)) & \
                          ((h - pd.concat([o, c], axis=1).max(axis=1)) < body)
        
        prev_c = c.shift(1); prev_o = o.shift(1)
        df['Is_Bull_Engulf'] = (c > o) & (prev_c < prev_o) & (c > prev_o) & (o < prev_c)
        df['Is_Bear_Engulf'] = (c < o) & (prev_c > prev_o) & (c < prev_o) & (o > prev_c)

        # Structure (Support/Resistance 50 Candle)
        df['Sup'] = df['low'].rolling(50).min()
        df['Res'] = df['high'].rolling(50).max()
        
        return df
    except: return df

# --- SCANNER (STRICT INSTITUTIONAL) ---
def scan_dynamic_market():
    try:
        exc = get_exchange()
        tickers = exc.fetch_tickers()
    except: return []

    valid_symbols = [s for s, d in tickers.items() if s.endswith('/USDT')]
    # Ambil Top 75 Koin Teraktif (Volatile)
    candidates_pool = sorted(valid_symbols, key=lambda x: tickers[x].get('quoteVolume', 0), reverse=True)[:75]
    
    final_picks = []
    
    for sym in candidates_pool:
        # Gunakan limit 500 saat scanning agar cepat namun tetap akurat
        df = fetch_market_data(sym, '1h', limit=500)
        df = calc_technical_indicators(df)
        
        if df is None or 'RSI' not in df.columns: continue
        
        poc = calc_volume_profile(df)
        last = df.iloc[-1]
        
        price = last['close']
        ema200 = last.get('EMA_200', 0)
        vol_sma = last.get('Vol_SMA', 0)
        rsi = last.get('RSI', 50)
        
        # Skip Market Sepi (Volume < 80% Rata-rata)
        if last['volume'] < (vol_sma * 0.8): continue
            
        bias = "NEUTRAL"; score = 0
        
        # LONG: Harga > EMA200 & Harga > POC
        if ema200 > 0 and price > ema200 and price > poc:
            if rsi < 65: 
                bias = "LONG"; score += 2
                if last['Is_Bull_Engulf']: score += 1
                
        # SHORT: Harga < EMA200 & Harga < POC
        elif ema200 > 0 and price < ema200 and price < poc:
            if rsi > 35:
                bias = "SHORT"; score += 2
                if last['Is_Bear_Engulf']: score += 1
                
        if bias != "NEUTRAL":
            final_picks.append({'symbol': sym, 'bias': bias, 'score': score, 'poc': poc})
            
    # Return Top 3
    final_picks = sorted(final_picks, key=lambda x: x['score'], reverse=True)
    return final_picks[:3]

# --- AI CONTEXT GENERATOR (LEARNING ENABLED) ---
def get_ai_context_indo(symbol, poc_val=0):
    # Tarik 1000 candle untuk analisa mendalam (Indikator Stabil)
    df_chart = fetch_market_data(symbol, '1h', limit=1000)
    df_trend = fetch_market_data(symbol, '1d', limit=1000)
    
    if df_chart is None: return None, "Error", 0
    
    df_chart = calc_technical_indicators(df_chart)
    df_trend = calc_technical_indicators(df_trend)
    
    if poc_val == 0: poc_val = calc_volume_profile(df_chart, bins=100)
        
    l_1h = df_chart.iloc[-1]
    l_1d = df_trend.iloc[-1]
    
    # Deteksi Pola Candle Text
    patt = []
    if l_1h['Is_Hammer']: patt.append("Hammer")
    if l_1h['Is_Bull_Engulf']: patt.append("Bullish Engulfing")
    if l_1h['Is_Bear_Engulf']: patt.append("Bearish Engulfing")
    candle_txt = ", ".join(patt) if patt else "Tidak ada pola signifikan"
    
    adaptive_rules = get_adaptive_rules()
    
    context = f"""
    [ATURAN DARI PENGALAMAN (ADAPTIVE LEARNING)]:
    Sistem telah belajar dari kesalahan user sebelumnya. PATUHI INI:
    {adaptive_rules if adaptive_rules else "Belum ada data pembelajaran. Analisa normal."}
    
    [DATA TEKNIKAL REAL-TIME {symbol}]:
    - Harga: {l_1h['close']}
    - POC (Volume Profile): {poc_val:.4f} (Harga di atas POC = Bullish, Bawah = Bearish)
    - RSI H1: {l_1h['RSI']:.2f}
    - Trend D1: {'BULLISH' if l_1d['close'] > l_1d['EMA_200'] else 'BEARISH'}
    - ATR: {l_1h['ATR']:.4f}
    
    [STRUKTUR HARGA]:
    - Pola Candle H1: {candle_txt}
    - Support Terdekat: {l_1h['Sup']}
    - Resistance Terdekat: {l_1h['Res']}
    
    [5 CANDLE TERAKHIR (OHLC)]:
    {df_chart.tail(5)[['open','high','low','close']].values.tolist()}
    """
    return df_chart, context, poc_val