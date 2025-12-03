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

# --- INDIKATOR LENGKAP v4.0 (Binance Standard) ---
def calc_technical_indicators(df):
    if df is None or df.empty: return None
    try:
        # 1. TREND (Binance Triple MA)
        df['MA_7'] = df.ta.sma(length=7)
        df['MA_25'] = df.ta.sma(length=25)
        df['MA_99'] = df.ta.sma(length=99)
        
        # 2. VOLATILITY (Bollinger Bands)
        bb = df.ta.bbands(length=20, std=2)
        if bb is not None:
            df['BB_Upper'] = bb.iloc[:, 0] # BBL
            df['BB_Mid'] = bb.iloc[:, 1]   # BBM
            df['BB_Lower'] = bb.iloc[:, 2] # BBU (urutan pandas_ta: Lower, Mid, Upper biasanya, cek nama kolom)
            # Koreksi: pandas_ta bbands returns columns like BBL_20_2.0, BBM_20_2.0, BBU_20_2.0
            # Kita ambil berdasarkan urutan kolom standar pandas_ta: Lower, Mid, Upper, Bandwidth, Percent
            df['BB_Lower'] = bb.iloc[:, 0]
            df['BB_Mid'] = bb.iloc[:, 1]
            df['BB_Upper'] = bb.iloc[:, 2]

        # 3. MOMENTUM
        df['RSI'] = df.ta.rsi(length=14)
        
        # 4. STOCH RSI
        stoch = df.ta.stochrsi(length=14, rsi_length=14, k=3, d=3)
        if stoch is not None:
            df['Stoch_K'] = stoch.iloc[:, 0]
            df['Stoch_D'] = stoch.iloc[:, 1]

        # 5. MACD
        macd = df.ta.macd(fast=12, slow=26, signal=9)
        if macd is not None:
            df['MACD'] = macd.iloc[:, 0]
            df['MACD_Hist'] = macd.iloc[:, 1]
        
        # 6. VOLUME & VOLATILITY
        df['ATR'] = df.ta.atr(length=14)
        df['Vol_SMA'] = df['volume'].rolling(20).mean()
        
        # 7. AUTO FIBONACCI
        recent_high = df['high'].rolling(100).max()
        recent_low = df['low'].rolling(100).min()
        df['Fib_0'] = recent_low
        df['Fib_1'] = recent_high
        diff = recent_high - recent_low
        df['Fib_0.618'] = recent_high - (diff * 0.618)
        df['Fib_0.5'] = recent_high - (diff * 0.5)

        # 8. CANDLE PATTERN (Math Logic)
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

# --- SCANNER (Tetap sama, sesuai dokumen Market Screening) ---
def scan_dynamic_market():
    try:
        exc = get_exchange()
        tickers = exc.fetch_tickers()
        candidates = []
        for symbol, data in tickers.items():
            if '/USDT' in symbol and 'UP/' not in symbol and 'DOWN/' not in symbol:
                change_pct = data.get('percentage')
                if change_pct is None: change_pct = 0.0
                vol_usdt = data.get('quoteVolume')
                if vol_usdt is None:
                    vol_usdt = (data.get('baseVolume') or 0) * (data.get('last') or 0)
                if vol_usdt > 10_000_000: 
                    candidates.append({
                        'symbol': symbol,
                        'change': float(change_pct),
                        'abs_change': abs(float(change_pct)), 
                        'volume': float(vol_usdt)
                    })
        top_10_volatile = sorted(candidates, key=lambda x: x['abs_change'], reverse=True)[:10]
        best_5_liquid = sorted(top_10_volatile, key=lambda x: x['volume'], reverse=True)[:5]
        
        final_picks = []
        for item in best_5_liquid:
            bias = "LONG (PUMP)" if item['change'] > 0 else "SHORT (DUMP)"
            final_picks.append({'symbol': item['symbol'], 'bias': bias, 'score': item['change']})
        return final_picks
    except Exception as e:
        print(f"Scanner Error: {e}")
        return []

# --- AI BRAIN & CONTEXT v4.0 ---
def get_ai_context_indo(symbol, poc_val=0):
    df_chart = fetch_market_data(symbol, '1h', limit=300)
    df_trend = fetch_market_data(symbol, '1d', limit=300)
    
    if df_chart is None: return None, "Error", 0
    
    df_chart = calc_technical_indicators(df_chart)
    df_trend = calc_technical_indicators(df_trend)
    
    if poc_val == 0: poc_val = calc_volume_profile(df_chart, bins=100)
    
    l_1h = df_chart.iloc[-1]
    l_1d = df_trend.iloc[-1]
    
    # Deteksi Pola Visual (Roboflow)
    vis_chart, vis_candle = detect_all_patterns(df_chart)
    
    # Deteksi Pola Math
    math_candle = "Normal"
    if l_1h.get('Hammer', 0) != 0: math_candle = "Hammer"
    elif l_1h.get('Engulfing', 0) != 0: math_candle = "Engulfing"
    
    fib_status = "Netral"
    price = l_1h['close']
    if 'Fib_0.618' in l_1h and abs(price - l_1h['Fib_0.618']) / price < 0.005: 
        fib_status = "Rejection di Golden Ratio 0.618"
    
    # Cek Volume Spike
    vol_status = "Normal"
    if l_1h['volume'] > (l_1h.get('Vol_SMA', 0) * 2):
        vol_status = "SPIKE DETECTED (>2x MA20)"

    adaptive_rules = get_adaptive_rules()
    
    context = f"""
    [HISTORY PEMBELAJARAN]:
    {adaptive_rules if adaptive_rules else "Belum ada history."}
    
    [ANALISA VISUAL (MATA AI)]:
    - Chart Pattern (Roboflow): {vis_chart}
    - Candle Pattern (Roboflow): {vis_candle}
    
    [DATA TEKNIKAL (LOGIKA MATH)]:
    - Harga Saat Ini: {price}
    - Trend MA (Binance Style):
      * MA 7: {l_1h.get('MA_7', 0):.2f}
      * MA 25: {l_1h.get('MA_25', 0):.2f}
      * MA 99: {l_1h.get('MA_99', 0):.2f}
    - Bollinger Bands (20, 2):
      * Upper: {l_1h.get('BB_Upper', 0):.2f}
      * Lower: {l_1h.get('BB_Lower', 0):.2f}
    - Candle Math Pattern: {math_candle}
    
    [INDIKATOR MOMENTUM]:
    - RSI (14): {l_1h.get('RSI', 50):.2f}
    - StochRSI: K={l_1h.get('Stoch_K', 0):.2f} / D={l_1h.get('Stoch_D', 0):.2f}
    - MACD Hist: {l_1h.get('MACD_Hist', 0):.4f}
    - Volume Status: {vol_status}
    
    [LAINNYA]:
    - POC (Volume Profile): {poc_val:.2f}
    - Fibs Status: {fib_status} (Fib 0.618: {l_1h.get('Fib_0.618', 0):.2f})
    
    [OHLC TERAKHIR (5 Candle)]:
    {df_chart.tail(5)[['open','high','low','close']].values.tolist()}
    """
    return df_chart, context, poc_val