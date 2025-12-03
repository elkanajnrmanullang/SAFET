import ccxt
import pandas as pd
import pandas_ta as ta
import numpy as np
from backend.database import get_adaptive_rules
from backend.vision_pattern import detect_all_patterns

# --- KONEKSI ---
def get_exchange():
    return ccxt.binance({
        'enableRateLimit': True, 
        'options': {'defaultType': 'future'}
    })

def get_market_overview():
    try:
        exc = get_exchange()
        btc = exc.fetch_ticker('BTC/USDT')
        return {'btc_price': btc['last'], 'btc_change': btc['percentage']}
    except: return {'btc_price': 0, 'btc_change': 0}

def fetch_market_data(symbol, timeframe='1h', limit=500):
    try:
        exc = get_exchange()
        bars = exc.fetch_ohlcv(symbol, timeframe, limit=limit)
        if not bars: return None
        df = pd.DataFrame(bars, columns=['timestamp','open','high','low','close','volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except: return None

# --- INDIKATOR ALTAQUANT v2.2 (Science-Based) ---
def calc_technical_indicators(df):
    if df is None or df.empty: return None
    try:
        # 1. TREND FILTER & VALUATION (MA Rules)
        # Cite: EMA 200 untuk Trend Jangka Panjang, EMA 50 untuk Value Zone
        df['EMA_50'] = df.ta.ema(length=50)
        df['EMA_200'] = df.ta.ema(length=200)
        
        # 2. MOMENTUM (RSI Tunggal)
        # Cite: RSI (14) untuk Divergence, tanpa StochRSI yang noisy
        df['RSI'] = df.ta.rsi(length=14)
        
        # 3. VOLATILITY & RISK (ATR)
        # Cite: Dynamic Stop Loss based on Volatility
        df['ATR'] = df.ta.atr(length=14)
        
        # 4. VOLUME VALIDATION
        # Cite: Breakout valid jika Volume > Rata-rata
        df['Vol_SMA'] = df['volume'].rolling(20).mean()
        
        # 5. KEY LEVELS (Support & Resistance Finder)
        # Mencari Fractal / Pivot High & Low untuk tabel S/R
        window = 10
        df['Pivot_High'] = df['high'].rolling(window*2+1, center=True).max()
        df['Pivot_Low'] = df['low'].rolling(window*2+1, center=True).min()
        
        # Hapus baris NaN di awal akibat calculation rolling
        df.dropna(inplace=True)
        
        return df
    except Exception as e:
        print(f"Err Indikator: {e}")
        return df

# --- CONTEXT BUILDER ---
def get_ai_context_indo(symbol, poc_val=0):
    df_chart = fetch_market_data(symbol, '1h', limit=300) # H1 untuk Trend Utama
    
    if df_chart is None: return None, "Error", 0
    
    df_chart = calc_technical_indicators(df_chart)
    l_1h = df_chart.iloc[-1]
    
    # 1. ANALISA TREND (EMA 200 Logic)
    price = l_1h['close']
    ema200 = l_1h['EMA_200']
    ema50 = l_1h['EMA_50']
    
    trend_status = "BULLISH (Harga > EMA 200)" if price > ema200 else "BEARISH (Harga < EMA 200)"
    value_gap = ((price - ema50) / ema50) * 100 # Jarak harga ke EMA 50 dalam %
    
    pullback_status = "Harga di Value Zone (Dekat EMA 50)" if abs(value_gap) < 1.0 else "Harga Over-Extended (Jauh dari EMA 50)"

    # 2. VOLUME CHECK
    vol_status = "SPIKE (Validasi Smart Money)" if l_1h['volume'] > l_1h['Vol_SMA'] else "Low/Normal"

    # 3. SUPPORT & RESISTANCE DATA
    # Ambil Pivot terakhir yang valid (bukan NaN)
    last_res = df_chart[df_chart['high'] == df_chart['Pivot_High']]['high'].iloc[-1] if not df_chart[df_chart['high'] == df_chart['Pivot_High']].empty else price * 1.05
    last_sup = df_chart[df_chart['low'] == df_chart['Pivot_Low']]['low'].iloc[-1] if not df_chart[df_chart['low'] == df_chart['Pivot_Low']].empty else price * 0.95

    # 4. VISION AI (Chart Pattern)
    vis_chart, _ = detect_all_patterns(df_chart)
    
    context = f"""
    [DATA PASAR REAL-TIME]:
    - Harga: {price}
    - ATR (Volatilitas): {l_1h['ATR']:.4f}
    
    [ANALISA TREND (EMA Rules)]:
    - EMA 200 (Trend Utama): {ema200:.2f} -> Status: {trend_status}
    - EMA 50 (Value Zone): {ema50:.2f} -> Status: {pullback_status}
    
    [MOMENTUM & VOLUME]:
    - RSI (14): {l_1h['RSI']:.2f}
    - Volume: {vol_status}
    
    [KEY LEVELS (Untuk Tabel)]:
    - Resistance Terdekat: {last_res}
    - Support Terdekat: {last_sup}
    
    [VISUAL PATTERN]:
    - AI Vision Detect: {vis_chart if vis_chart else "Tidak ada pola jelas"}
    
    [OHLC TERAKHIR (5 Candle)]:
    {df_chart.tail(5)[['open','high','low','close']].values.tolist()}
    """
    return df_chart, context, 0

# Scanner sederhana untuk mendapatkan kandidat
def scan_dynamic_market():
    try:
        exc = get_exchange()
        tickers = exc.fetch_tickers()
        candidates = []
        for s, d in tickers.items():
            if '/USDT' in s and d['quoteVolume'] > 10_000_000:
                candidates.append({'symbol': s, 'change': d['percentage']})
        return sorted(candidates, key=lambda x: abs(x['change']), reverse=True)[:5]
    except: return []