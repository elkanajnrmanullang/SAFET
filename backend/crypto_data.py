import ccxt
import pandas as pd
import pandas_ta as ta

def get_binance_data(symbol, timeframe, limit=500):
    """
    Menarik data dari Binance.
    """
    try:
        exchange = ccxt.binance()
        bars = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        if not bars: return None
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except:
        return None

def calculate_indicators(df):
    """
    Menghitung indikator teknikal.
    """
    if df is None or df.empty: return None
    try:
        df['RSI'] = df.ta.rsi(length=14)
        df['EMA_50'] = df.ta.ema(length=50)
        df['EMA_200'] = df.ta.ema(length=200)
        macd = df.ta.macd(fast=12, slow=26, signal=9)
        if macd is not None: df = pd.concat([df, macd], axis=1)
        df.dropna(inplace=True)
        return df
    except:
        return df

def get_mtf_analysis(symbol, main_tf):
    """
    FITUR BARU: Mengambil data Multi-Timeframe (MTF).
    Misal user pilih 1h (Entry), sistem otomatis ambil 4h (Trend).
    """
    # 1. Tentukan Timeframe Pendamping (Higher High)
    tf_map = {
        '15m': '1h',
        '1h':  '4h',
        '4h':  '1d',
        '1d':  '1w'
    }
    higher_tf = tf_map.get(main_tf, '1d') # Default ke 1d jika tidak ketemu

    # 2. Tarik Data Utama (Entry)
    df_main = get_binance_data(symbol, main_tf)
    df_main = calculate_indicators(df_main)
    
    # 3. Tarik Data Trend (Higher TF)
    df_trend = get_binance_data(symbol, higher_tf)
    df_trend = calculate_indicators(df_trend)

    if df_main is None or df_trend is None:
        return None, "Gagal menarik data."

    # 4. Ambil baris terakhir
    main = df_main.iloc[-1]
    trend = df_trend.iloc[-1]

    # Helper untuk ambil nama kolom MACD yg dinamis
    def get_macd(row, df_cols):
        col = [c for c in df_cols if 'MACD_' in c and 'h' not in c and 's' not in c][0]
        sig = [c for c in df_cols if 'MACDs_' in c][0]
        return row[col], row[sig]

    main_macd, main_sig = get_macd(main, df_main.columns)
    trend_macd, trend_sig = get_macd(trend, df_trend.columns)

    # 5. Susun Laporan Data Lengkap
    data_summary = f"""
    ANALISA MULTI-TIMEFRAME UNTUK {symbol}:
    
    1. TIMEFRAME UTAMA ({main_tf}) - FOKUS MOMENTUM/ENTRY:
    - Harga: {main['close']}
    - RSI: {main['RSI']:.2f}
    - EMA 50 vs 200: {main['EMA_50']:.2f} vs {main['EMA_200']:.2f}
    - MACD: {main_macd:.2f} (Signal: {main_sig:.2f})

    2. TIMEFRAME TREN BESAR ({higher_tf}) - FOKUS ARAH PASAR:
    - RSI: {trend['RSI']:.2f}
    - EMA 50 vs 200: {trend['EMA_50']:.2f} vs {trend['EMA_200']:.2f} (Posisi harga terhadap EMA menentukan tren besar)
    - MACD: {trend_macd:.2f}
    """
    
    return df_main, data_summary