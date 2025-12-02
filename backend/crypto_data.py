import ccxt
import pandas as pd
import pandas_ta as ta
import numpy as np
from backend.database import get_adaptive_rules
from backend.vision_pattern import detect_all_patterns

# --- KONEKSI ---
def get_exchange():
    # Menggunakan opsi 'future' agar sesuai dengan data Binance Futures
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

def calc_volume_profile(df, bins=100):
    try:
        price_min = df['low'].min(); price_max = df['high'].max()
        price_range = np.linspace(price_min, price_max, bins)
        vol_profile = np.zeros(bins-1)
        for i in range(len(df)):
            idx = np.digitize(df['close'].iloc[i], price_range) - 1
            if 0 <= idx < len(vol_profile): vol_profile[idx] += df['volume'].iloc[i]
        return (price_range[np.argmax(vol_profile)] + price_range[np.argmax(vol_profile)+1]) / 2
    except: return df['close'].iloc[-1]

# --- INDIKATOR LENGKAP v3.3 ---
def calc_technical_indicators(df):
    if df is None or df.empty: return None
    try:
        # 1. TREND
        df['EMA_50'] = df.ta.ema(length=50)
        df['EMA_200'] = df.ta.ema(length=200)
        
        # 2. MOMENTUM
        df['RSI'] = df.ta.rsi(length=14)
        
        # 3. STOCH RSI
        stoch = df.ta.stochrsi(length=14, rsi_length=14, k=3, d=3)
        if stoch is not None:
            df['Stoch_K'] = stoch.iloc[:, 0]
            df['Stoch_D'] = stoch.iloc[:, 1]

        # 4. MACD
        macd = df.ta.macd(fast=12, slow=26, signal=9)
        if macd is not None:
            df['MACD'] = macd.iloc[:, 0]
            df['MACD_Hist'] = macd.iloc[:, 1]
        
        # 5. VOLATILITY
        df['ATR'] = df.ta.atr(length=14)
        df['Vol_SMA'] = df['volume'].rolling(20).mean()
        
        # 6. AUTO FIBONACCI
        recent_high = df['high'].rolling(100).max()
        recent_low = df['low'].rolling(100).min()
        df['Fib_0'] = recent_low
        df['Fib_1'] = recent_high
        diff = recent_high - recent_low
        df['Fib_0.618'] = recent_high - (diff * 0.618)
        df['Fib_0.5'] = recent_high - (diff * 0.5)

        # 7. CANDLE PATTERN
        hammer_pat = df.ta.cdl_pattern(name="hammer")
        engulf_pat = df.ta.cdl_pattern(name="engulfing")
        
        if hammer_pat is not None: df['Hammer'] = hammer_pat.iloc[:, 0]
        else: df['Hammer'] = 0
            
        if engulf_pat is not None: df['Engulfing'] = engulf_pat.iloc[:, 0]
        else: df['Engulfing'] = 0
        
        return df
    except Exception as e:
        print(f"Err Indikator: {e}")
        return df

# --- SCANNER FIXED (Top 10 Gainers/Losers -> 5 Best Liquid) ---
def scan_dynamic_market():
    """
    1. Ambil semua ticker Futures.
    2. Filter symbol yang valid (USDT pair).
    3. Urutkan berdasarkan ABSOLUTE % CHANGE (Mencari Top Gainers & Top Losers).
    4. Ambil Top 10 paling bergerak.
    5. Dari 10 itu, ambil 5 dengan Volume (Quote USDT) terbesar.
    """
    try:
        exc = get_exchange()
        tickers = exc.fetch_tickers()
        
        candidates = []
        
        for symbol, data in tickers.items():
            # Filter hanya pair USDT dan hindari pair aneh (seperti index leverage)
            if '/USDT' in symbol and 'UP/' not in symbol and 'DOWN/' not in symbol:
                
                # Handle data None/Kosong dengan aman
                change_pct = data.get('percentage')
                if change_pct is None: change_pct = 0.0
                
                # Gunakan quoteVolume (Volume dalam USDT) jika ada, jika tidak pakai baseVolume * price
                vol_usdt = data.get('quoteVolume')
                if vol_usdt is None:
                    vol_usdt = (data.get('baseVolume') or 0) * (data.get('last') or 0)
                
                # Filter koin dengan volume terlalu kecil (misal di bawah $10jt) agar tidak terjebak koin gorengan
                if vol_usdt > 10_000_000: 
                    candidates.append({
                        'symbol': symbol,
                        'change': float(change_pct),
                        'abs_change': abs(float(change_pct)), # Mutlak agar minus besar juga masuk
                        'volume': float(vol_usdt)
                    })
        
        # TAHAP 1: Ambil 10 Koin dengan Pergerakan Terbesar (Top Volatility)
        # Sort desc berdasarkan abs_change
        top_10_volatile = sorted(candidates, key=lambda x: x['abs_change'], reverse=True)[:10]
        
        # TAHAP 2: Dari 10 itu, pilih 5 yang paling Likuid (Volume Terbesar)
        # Sort desc berdasarkan volume
        best_5_liquid = sorted(top_10_volatile, key=lambda x: x['volume'], reverse=True)[:5]
        
        final_picks = []
        for item in best_5_liquid:
            bias = "LONG (PUMP)" if item['change'] > 0 else "SHORT (DUMP)"
            final_picks.append({
                'symbol': item['symbol'], 
                'bias': bias, 
                'score': item['change']
            })
            
        print(f"Scanner Result: {[x['symbol'] for x in final_picks]}") # Debug log di terminal
        return final_picks

    except Exception as e:
        print(f"Scanner Error: {e}")
        return []

# --- AI BRAIN & CONTEXT ---
def get_ai_context_indo(symbol, poc_val=0):
    # Gunakan fungsi yang sudah ada
    df_chart = fetch_market_data(symbol, '1h', limit=300)
    df_trend = fetch_market_data(symbol, '1d', limit=300)
    
    if df_chart is None: return None, "Error", 0
    
    df_chart = calc_technical_indicators(df_chart)
    df_trend = calc_technical_indicators(df_trend)
    
    if poc_val == 0: poc_val = calc_volume_profile(df_chart, bins=100)
    
    l_1h = df_chart.iloc[-1]
    l_1d = df_trend.iloc[-1]
    
    vis_chart, vis_candle = detect_all_patterns(df_chart)
    
    math_candle = "Normal"
    if l_1h.get('Hammer', 0) != 0: math_candle = "Hammer"
    elif l_1h.get('Engulfing', 0) != 0: math_candle = "Engulfing"
    
    fib_status = "Netral"
    price = l_1h['close']
    if 'Fib_0.618' in l_1h and abs(price - l_1h['Fib_0.618']) / price < 0.005: 
        fib_status = "Rejection di Golden Ratio 0.618"
    
    adaptive_rules = get_adaptive_rules()
    
    context = f"""
    [HISTORY PEMBELAJARAN]:
    {adaptive_rules if adaptive_rules else "Belum ada history."}
    
    [ANALISA VISUAL (MATA)]:
    - Chart Pattern: {vis_chart}
    - Candle Pattern: {vis_candle}
    
    [DATA TEKNIKAL (LOGIKA)]:
    - Harga: {price}
    - Trend D1: {'BULLISH' if 'EMA_200' in l_1d and l_1d['close'] > l_1d['EMA_200'] else 'BEARISH'}
    - EMA 200 H1: {l_1h.get('EMA_200', 0):.2f}
    - Candle Math: {math_candle}
    
    [INDIKATOR]:
    - RSI (14): {l_1h.get('RSI', 50):.2f}
    - StochRSI: K={l_1h.get('Stoch_K', 0):.2f} / D={l_1h.get('Stoch_D', 0):.2f}
    - MACD Hist: {l_1h.get('MACD_Hist', 0):.4f}
    
    [LAINNYA]:
    - POC: {poc_val:.2f}
    - Fibs: {fib_status}
    
    [OHLC TERAKHIR]:
    {df_chart.tail(5)[['open','high','low','close']].values.tolist()}
    """
    return df_chart, context, poc_val