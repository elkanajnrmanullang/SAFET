import ccxt
import pandas as pd
import pandas_ta as ta

# --- KONEKSI BINANCE ---
def fetch_binance_data(symbol, timeframe, limit=300):
    try:
        exc = ccxt.binance({
            'enableRateLimit': True, 
            'timeout': 30000, 
            'options': {'defaultType': 'future'}
        })
        exc.ssl = False; exc.verify = False 
        
        bars = exc.fetch_ohlcv(symbol, timeframe, limit=limit)
        if not bars: return None
            
        df = pd.DataFrame(bars, columns=['timestamp','open','high','low','close','volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        print(f"Connection Warning {symbol}: {e}") 
        return None

# --- MARKET OVERVIEW ---
def get_market_overview():
    try:
        exc = ccxt.binance()
        btc = exc.fetch_ticker('BTC/USDT')
        return {'btc_price': btc['last'], 'btc_change': btc['percentage']}
    except:
        return {'btc_price': 0, 'btc_change': 0}

# --- INDIKATOR & POLA MATEMATIS ---
def calc_indicators(df):
    if df is None or df.empty: return None
    try:
        # Indikator Dasar
        df['RSI'] = df.ta.rsi(length=14)
        df['EMA_50'] = df.ta.ema(length=50)
        df['EMA_200'] = df.ta.ema(length=200)
        df['ATR'] = df.ta.atr(length=14)
        df['Sup'] = df['low'].rolling(50).min() # Support 50 candle
        df['Res'] = df['high'].rolling(50).max() # Resistance 50 candle
        
        # --- DETEKSI POLA CANDLE (ALGORITMA PYTHON) ---
        o = df['open']; c = df['close']; h = df['high']; l = df['low']
        body = abs(c - o)
        
        # 1. Hammer (Reversal Bullish)
        lower_wick = pd.concat([o, c], axis=1).min(axis=1) - l
        df['Is_Hammer'] = (lower_wick > (body * 2)) & ((h - pd.concat([o, c], axis=1).max(axis=1)) < body)
        
        # 2. Shooting Star (Reversal Bearish)
        upper_wick = h - pd.concat([o, c], axis=1).max(axis=1)
        df['Is_Star'] = (upper_wick > (body * 2)) & ((pd.concat([o, c], axis=1).min(axis=1) - l) < body)
        
        # 3. Engulfing (Bullish & Bearish)
        prev_c = c.shift(1); prev_o = o.shift(1)
        df['Is_Bull_Engulf'] = (c > o) & (prev_c < prev_o) & (c > prev_o) & (o < prev_c)
        df['Is_Bear_Engulf'] = (c < o) & (prev_c > prev_o) & (c < prev_o) & (o > prev_c)

        return df
    except Exception as e: 
        return df

# --- SCANNER ---
def scan_dynamic_market():
    try:
        exc = ccxt.binance({'options': {'defaultType': 'future'}, 'timeout': 30000})
        exc.ssl = False; exc.verify = False
        tickers = exc.fetch_tickers()
    except: return []

    valid_symbols = []
    for symbol, data in tickers.items():
        if symbol.endswith('/USDT') and data['quoteVolume'] is not None:
            if data['quoteVolume'] > 20000000:
                valid_symbols.append(symbol)

    top_volatile = sorted(valid_symbols, key=lambda x: abs(tickers[x]['percentage'] or 0), reverse=True)[:50]
    candidates = []
    
    for sym in top_volatile:
        df = fetch_binance_data(sym, '1h', limit=100)
        df = calc_indicators(df)
        
        if df is None or 'RSI' not in df.columns: continue
        
        last = df.iloc[-1]
        price = last['close']
        ema200 = last.get('EMA_200', 0)
        rsi = last.get('RSI', 50)
        
        bias = "NEUTRAL"; score = 0
        
        if ema200 > 0 and price > ema200:
            if rsi < 65: bias = "LONG"; score = (70 - rsi)
        elif ema200 > 0 and price < ema200:
            if rsi > 35: bias = "SHORT"; score = (rsi - 30)

        if bias != "NEUTRAL":
            candidates.append({'symbol': sym, 'bias': bias, 'score': score})
            
    candidates = sorted(candidates, key=lambda x: x['score'], reverse=True)
    return candidates[:3]

# --- AI CONTEXT PREP (DATA BESAR 150 CANDLE) ---
def get_ai_context_indo(symbol):
    df_chart = fetch_binance_data(symbol, '1h', limit=300) # Tarik 300 agar aman
    df_trend = fetch_binance_data(symbol, '1d', limit=300)
    
    if df_chart is None or df_trend is None: return None, "Data Error"
    
    df_chart = calc_indicators(df_chart)
    df_trend = calc_indicators(df_trend)
    
    l_1h = df_chart.iloc[-1]
    l_1d = df_trend.iloc[-1]
    
    # 1. Info Pola Candle Terakhir (Dari Algoritma Python)
    patt = []
    if l_1h['Is_Hammer']: patt.append("Hammer (Potensi Reversal Naik)")
    if l_1h['Is_Star']: patt.append("Shooting Star (Potensi Reversal Turun)")
    if l_1h['Is_Bull_Engulf']: patt.append("Bullish Engulfing (Kuat Naik)")
    if l_1h['Is_Bear_Engulf']: patt.append("Bearish Engulfing (Kuat Turun)")
    candle_algo_txt = ", ".join(patt) if patt else "Normal Candle"

    # 2. DATA STRUKTUR HARGA (150 Candle Terakhir = 6 Hari Data H1)
    # Format: [Open, High, Low, Close]
    # AI akan menggunakan ini untuk menggambar Support/Resistance dan Chart Pattern
    history_long = df_chart.tail(150)[['open', 'high', 'low', 'close']].values.tolist()
    
    context = f"""
    DATA TERKINI BINANCE:
    - Symbol: {symbol}
    - Harga: {l_1h['close']}
    
    INDIKATOR TEKNIKAL:
    - RSI: {l_1h['RSI']:.2f}
    - EMA 50: {l_1h['EMA_50']:.2f}
    - EMA 200: {l_1h['EMA_200']:.2f}
    - Support Terdekat (50 Candle): {l_1h['Sup']}
    - Resistance Terdekat (50 Candle): {l_1h['Res']}
    
    DETEKSI ALGORITMA CANDLESTICK (Saat ini):
    - {candle_algo_txt}
    
    DATA MENTAH 150 CANDLE TERAKHIR (Untuk Analisa Chart Pattern Besar):
    Gunakan data ini untuk mencari pola besar seperti Head & Shoulders, Flags, Wedges, atau Supply/Demand Zone.
    DATA: {history_long}
    """
    return df_chart, context