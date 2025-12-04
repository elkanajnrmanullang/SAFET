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

def fetch_market_data(symbol, timeframe='1h', limit=1000):
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
def get_ai_context_indo(symbol, preferred_tf='1h'):
    # Daftar prioritas timeframe untuk dicek
    # Jika user minta spesifik (misal di UI pilih M5), list ini bisa di-override
    scan_sequence = ['1h', '30m', '15m']
    
    selected_df = None
    selected_tf = '1h'
    final_context = ""
    is_valid_setup = False
    
    # --- LOOPING CEK TIMEFRAME ---
    for tf in scan_sequence:
        # Ambil data
        df = fetch_market_data(symbol, tf, limit=1000)
        if df is None: continue
        
        # Hitung Indikator
        df = calc_technical_indicators(df)
        last_row = df.iloc[-1]
        
        # Cek Syarat Pullback: Jarak harga ke EMA 50 < 1.1%
        price = last_row['close']
        ema50 = last_row['EMA_50']
        gap_percent = abs((price - ema50) / ema50) * 100
        
        # Jika ketemu kondisi Pullback (Gap < 1.1%), STOP mencari
        if gap_percent < 1.1:
            selected_df = df
            selected_tf = tf
            is_valid_setup = True
            break # KELUAR DARI LOOP, kita pakai timeframe ini!
    
    # --- FALLBACK JIKA TIDAK ADA YG COCOK ---
    # Jika sampai loop selesai tidak ada yg pullback, pakai H1 (atau TF pertama)
    if selected_df is None:
        selected_tf = scan_sequence[0]
        selected_df = fetch_market_data(symbol, selected_tf, limit=1000)
        if selected_df is not None:
            selected_df = calc_technical_indicators(selected_df)
            
    if selected_df is None: return None, "Error Data", selected_tf

    # --- GENERATE CONTEXT UNTUK AI (Pakai Data Terpilih) ---
    l_last = selected_df.iloc[-1]
    price = l_last['close']
    ema200 = l_last['EMA_200']
    ema50 = l_last['EMA_50']
    
    trend_status = "BULLISH" if price > ema200 else "BEARISH"
    
    # Hitung ulang status untuk teks
    gap_final = abs((price - ema50) / ema50) * 100
    pullback_msg = "✅ VALID PULLBACK (Harga di Value Zone)" if gap_final < 1.1 else "⚠️ NO SETUP (Harga Jauh dari EMA 50)"

    # Kita tambahkan info TIMEFRAME di prompt agar AI sadar
    context = f"""
    [DATA PASAR REAL-TIME]:
    - Timeframe Terpilih: {selected_tf} (Otomatis by System)
    - Harga: {price}
    - Status Setup: {pullback_msg}
    
    [ANALISA TREND ({selected_tf})]:
    - EMA 200 (Trend): {ema200:.2f} -> {trend_status}
    - EMA 50 (Value): {ema50:.2f} -> Gap: {gap_final:.2f}%
    
    [MOMENTUM]:
    - RSI (14): {l_last['RSI']:.2f}
    - Volume Spike: {"YA" if l_last['volume'] > l_last['Vol_SMA'] else "TIDAK"}

    [OHLC TERAKHIR]:
    {selected_df.tail(5)[['open','high','low','close']].values.tolist()}
    """
    
    # Return 3 hal: DataFrame, Teks Context, dan Timeframe yang akhirnya dipakai
    return selected_df, context, selected_tf

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