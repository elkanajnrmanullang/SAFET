import ccxt
import pandas as pd
import pandas_ta as ta
import numpy as np
from backend.database import get_adaptive_rules

# --- KONEKSI GLOBAL ---
def get_exchange():
    return ccxt.binance({'enableRateLimit': True, 'timeout': 30000, 'options': {'defaultType': 'future'}})

# --- MARKET OVERVIEW ---
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

# --- VOLUME PROFILE (POC) ---
def calc_volume_profile(df, bins=100):
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
        return (price_range[max_vol_idx] + price_range[max_vol_idx+1]) / 2
    except:
        return df['close'].iloc[-1]

# --- FETCH DATA ---
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

# --- INDIKATOR INSTITUSIONAL (CLEAN & STANDARD) ---
def calc_technical_indicators(df):
    if df is None or df.empty: return None
    try:
        # 1. TREND: EMA 200 (King of Trend) & EMA 50 (Intermediate)
        df['EMA_50'] = df.ta.ema(length=50)
        df['EMA_200'] = df.ta.ema(length=200)
        
        # 2. MOMENTUM: RSI 14 (Standard Industry)
        df['RSI'] = df.ta.rsi(length=14)
        
        # 3. CONFIRMATION: MACD (12, 26, 9)
        macd = df.ta.macd(fast=12, slow=26, signal=9)
        if macd is not None:
            # MACD Line, Histogram, Signal
            df['MACD'] = macd.iloc[:, 0]
            df['MACD_Hist'] = macd.iloc[:, 1]
            df['MACD_Signal'] = macd.iloc[:, 2]
        
        # 4. VOLATILITY: ATR
        df['ATR'] = df.ta.atr(length=14)
        
        # 5. VOLUME: SMA Volume
        df['Vol_SMA'] = df['volume'].rolling(20).mean()
        
        # 6. PRICE ACTION: Patterns
        o = df['open']; c = df['close']; h = df['high']; l = df['low']
        body = abs(c - o)
        
        df['Is_Hammer'] = ((pd.concat([o, c], axis=1).min(axis=1) - l) > (body * 2)) & \
                          ((h - pd.concat([o, c], axis=1).max(axis=1)) < body)
                          
        prev_c = c.shift(1); prev_o = o.shift(1)
        df['Is_Bull_Engulf'] = (c > o) & (prev_c < prev_o) & (c > prev_o) & (o < prev_c)
        df['Is_Bear_Engulf'] = (c < o) & (prev_c > prev_o) & (c < prev_o) & (o > prev_c)

        # Structure
        df['Sup'] = df['low'].rolling(50).min()
        df['Res'] = df['high'].rolling(50).max()
        
        return df
    except: return df

# --- SCANNER (PRO-GRADE LOGIC) ---
def scan_dynamic_market():
    try:
        exc = get_exchange()
        tickers = exc.fetch_tickers()
    except: return []

    # 1. Filter Likuiditas (> $30M)
    valid_symbols = []
    for symbol, data in tickers.items():
        if symbol.endswith('/USDT') and data.get('quoteVolume') is not None:
            if data['quoteVolume'] > 30000000: 
                valid_symbols.append(symbol)

    # 2. Sort by Volatility (Top 60)
    candidates_pool = sorted(valid_symbols, key=lambda x: abs(tickers[x].get('percentage', 0) or 0), reverse=True)[:60]
    
    final_picks = []
    
    for sym in candidates_pool:
        df = fetch_market_data(sym, '1h', limit=300) # Cukup 300 untuk scan cepat
        df = calc_technical_indicators(df)
        
        if df is None or 'RSI' not in df.columns: continue
        
        poc = calc_volume_profile(df, bins=50)
        last = df.iloc[-1]
        
        price = last['close']
        ema200 = last.get('EMA_200', 0)
        ema50 = last.get('EMA_50', 0)
        rsi = last.get('RSI', 50)
        macd_hist = last.get('MACD_Hist', 0)
        
        bias = "NEUTRAL"; score = 0
        
        # --- INSTITUTIONAL STRATEGY: TREND CONTINUATION ---
        
        # LONG SETUP:
        # 1. Harga > EMA 200 (Bull Market)
        # 2. Harga > POC (Volume Support)
        # 3. RSI 'Reset' (40-60) atau Oversold (<30) - BUKAN Overbought (>70)
        # 4. MACD Histogram Positif (Momentum Naik)
        if ema200 > 0 and price > ema200 and price > poc:
            if rsi < 65 and macd_hist > 0:
                bias = "LONG"
                score += 2
                if last['Is_Bull_Engulf']: score += 1
                if price > ema50: score += 1 # Strong Trend
                
        # SHORT SETUP:
        # 1. Harga < EMA 200 (Bear Market)
        # 2. Harga < POC (Volume Resistance)
        # 3. RSI 'Reset' (40-60) atau Overbought (>70) - BUKAN Oversold (<30)
        # 4. MACD Histogram Negatif (Momentum Turun)
        elif ema200 > 0 and price < ema200 and price < poc:
            if rsi > 35 and macd_hist < 0:
                bias = "SHORT"
                score += 2
                if last['Is_Bear_Engulf']: score += 1
                if price < ema50: score += 1 # Strong Trend

        if bias != "NEUTRAL":
            final_picks.append({'symbol': sym, 'bias': bias, 'score': score, 'poc': poc})
            
    # Return Top 3 Best Setups
    final_picks = sorted(final_picks, key=lambda x: x['score'], reverse=True)
    return final_picks[:3]

# --- AI CONTEXT GENERATOR ---
def get_ai_context_indo(symbol, poc_val=0):
    df_chart = fetch_market_data(symbol, '1h', limit=1000)
    df_trend = fetch_market_data(symbol, '1d', limit=1000)
    
    if df_chart is None: return None, "Error", 0
    
    df_chart = calc_technical_indicators(df_chart)
    df_trend = calc_technical_indicators(df_trend)
    
    if poc_val == 0: poc_val = calc_volume_profile(df_chart, bins=100)
        
    l_1h = df_chart.iloc[-1]
    l_1d = df_trend.iloc[-1]
    
    patt = []
    if l_1h['Is_Hammer']: patt.append("Hammer (Bullish)")
    if l_1h['Is_Bull_Engulf']: patt.append("Bullish Engulfing")
    if l_1h['Is_Bear_Engulf']: patt.append("Bearish Engulfing")
    candle_txt = ", ".join(patt) if patt else "Netral"
    
    adaptive_rules = get_adaptive_rules()
    atr = l_1h.get('ATR', l_1h['close']*0.01)
    
    context = f"""
    [HISTORY PEMBELAJARAN]:
    {adaptive_rules if adaptive_rules else "Analisa standar."}
    
    [DATA TEKNIKAL PROFESIONAL {symbol}]:
    - Harga: {l_1h['close']}
    - POC (Volume Profile): {poc_val:.4f}
    
    [INDIKATOR UTAMA]:
    - EMA 200 (Trend King): {l_1h['EMA_200']:.2f} (Harga {'DI ATAS' if l_1h['close'] > l_1h['EMA_200'] else 'DI BAWAH'})
    - RSI 14 (Momentum): {l_1h['RSI']:.2f} (Zona: {'OVERSOLD' if l_1h['RSI']<30 else 'OVERBOUGHT' if l_1h['RSI']>70 else 'NETRAL'})
    - MACD Histogram: {l_1h.get('MACD_Hist', 0):.4f} ({'Momentum Bullish' if l_1h.get('MACD_Hist', 0) > 0 else 'Momentum Bearish'})
    
    [STRUKTUR]:
    - Pola Candle: {candle_txt}
    - Support Terdekat: {l_1h['Sup']}
    - Resistance Terdekat: {l_1h['Res']}
    - ATR (Volatilitas): {atr:.4f}
    
    [150 CANDLE HISTORY (OHLC)]:
    {df_chart.tail(150)[['open','high','low','close']].values.tolist()}
    """
    return df_chart, context, poc_val