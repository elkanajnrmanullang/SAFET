import ccxt
import yfinance as yf
import pandas as pd
import pandas_ta as ta

# --- DATA FETCHING ENGINE ---
def fetch_data_and_news(symbol, timeframe, limit=200):
    symbol_yf = symbol.replace("/", "-").replace("USDT", "USD")
    tf_map = {'15m': '15m', '1h': '1h', '4h': '1h', '1d': '1d'}
    
    try:
        exc = ccxt.binance({'enableRateLimit':True, 'timeout':5000})
        exc.ssl = False; exc.verify = False
        bars = exc.fetch_ohlcv(symbol, timeframe, limit=limit)
        if bars:
            df = pd.DataFrame(bars, columns=['timestamp','open','high','low','close','volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df, "Binance Data", ""
    except: pass

    try:
        tick = yf.Ticker(symbol_yf)
        period = '1y' if timeframe == '1d' else '2mo'
        df = tick.history(period=period, interval=tf_map.get(timeframe, '1h'))
        
        news_text = ""
        if tick.news:
            for n in tick.news[:2]:
                news_text += f"- {n.get('title')}\n"
        
        if not df.empty:
            df = df.reset_index()
            df = df.rename(columns={'Date':'timestamp','Datetime':'timestamp','Open':'open','High':'high','Low':'low','Close':'close','Volume':'volume'})
            df['timestamp'] = df['timestamp'].dt.tz_localize(None)
            return df.tail(limit), "Yahoo Data", news_text
    except: pass

    return None, None, None

# --- MARKET DASHBOARD (UI AWAL) ---
def get_market_overview():
    # Mengambil data BTC & ETH singkat untuk tampilan awal
    try:
        exc = ccxt.binance()
        exc.ssl = False; exc.verify = False
        btc = exc.fetch_ticker('BTC/USDT')
        eth = exc.fetch_ticker('ETH/USDT')
        return {
            'btc_price': btc['last'],
            'btc_change': btc['percentage'],
            'eth_price': eth['last'],
            'eth_change': eth['percentage']
        }
    except:
        return {'btc_price': 0, 'btc_change': 0, 'eth_price': 0, 'eth_change': 0}

# --- INDICATORS ---
def calc_indicators(df):
    if df is None or df.empty: return None
    try:
        df['RSI'] = df.ta.rsi(length=14)
        df['EMA_50'] = df.ta.ema(length=50)
        df['EMA_200'] = df.ta.ema(length=200)
        df['Sup'] = df['low'].rolling(50).min()
        df['Res'] = df['high'].rolling(50).max()
        return df
    except: return df

# --- SCANNER TOTAL ---
def scan_dynamic_market():
    try:
        exc = ccxt.binance()
        tickers = exc.fetch_tickers()
    except: return []

    valid_symbols = []
    for symbol, data in tickers.items():
        if symbol.endswith('/USDT') and data['quoteVolume'] is not None:
            if data['quoteVolume'] > 30000000:
                valid_symbols.append(symbol)

    top_50_symbols = sorted(valid_symbols, key=lambda x: tickers[x]['quoteVolume'], reverse=True)[:50]
    candidates = []
    
    for sym in top_50_symbols:
        df, _, _ = fetch_data_and_news(sym, '1h', limit=100)
        df = calc_indicators(df)
        
        if df is None or 'RSI' not in df.columns: continue
        
        last = df.iloc[-1]
        price = last['close']
        ema200 = last.get('EMA_200', 0)
        rsi = last.get('RSI', 50)
        bias = "NEUTRAL"; rr = 0
        
        if ema200 > 0 and price > ema200 and rsi < 45:
            sup = last.get('Sup', price * 0.95)
            res = last.get('Res', price * 1.05)
            risk = price - sup; reward = res - price
            if risk > 0: rr = reward / risk
            if rr >= 1.5: bias = "LONG"
            
        elif ema200 > 0 and price < ema200 and rsi > 55:
            sup = last.get('Sup', price * 0.95)
            res = last.get('Res', price * 1.05)
            risk = res - price; reward = price - sup
            if risk > 0: rr = reward / risk
            if rr >= 1.5: bias = "SHORT"

        if bias != "NEUTRAL":
            candidates.append({'symbol': sym, 'bias': bias, 'rr': round(rr, 2), 'price': price})
            
    candidates = sorted(candidates, key=lambda x: x['rr'], reverse=True)
    return candidates[:3]

# --- AI DATA PREP ---
def get_ai_context_indo(symbol):
    df_chart, src, news = fetch_data_and_news(symbol, '1h', limit=200)
    df_trend, _, _ = fetch_data_and_news(symbol, '1d', limit=200)
    
    if df_chart is None: return None, "Data Error"
    
    df_chart = calc_indicators(df_chart)
    df_trend = calc_indicators(df_trend)
    
    l_1h = df_chart.iloc[-1]
    l_1d = df_trend.iloc[-1]
    candles = df_chart.tail(5)[['open','high','low','close']].values.tolist()
    
    context = f"""
    BERITA TERBARU: {news if news else "Gunakan sentimen makro."}
    MARKET (H1): Price:{l_1h['close']}, RSI:{l_1h['RSI']:.2f}, EMA200:{l_1h['EMA_200']:.2f}
    TREND (D1): {'BULLISH' if l_1d['close'] > l_1d['EMA_200'] else 'BEARISH'}
    CANDLES (5): {candles}
    """
    return df_chart, context