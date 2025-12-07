import pandas as pd
import pandas_ta as ta
import numpy as np

# ================================================================
# BASIC INDICATOR LOGIC
# ================================================================
def compute_atr(df, length=14):
    try:
        atr_series = ta.atr(df["high"], df["low"], df["close"], length)
        return float(atr_series.iloc[-1])
    except:
        return 0.0

def compute_volume_ma(df, length=20):
    return df["volume"].rolling(length).mean()

# ================================================================
# HIGH-LEVEL TF-BASED INDICATORS
# ================================================================
def apply_indicators_by_tf(df, tf):
    """
    Apply indicators based on specific Timeframe requirements.
    """
    df = df.copy()

    # 1. Global Indicator
    df["Vol_MA20"] = compute_volume_ma(df, 20)

    # 2. H4 (Anchor): EMA50, EMA200, ADX
    if tf == "4h":
        df["EMA50"] = ta.ema(df["close"], 50)
        df["EMA200"] = ta.ema(df["close"], 200)
        adx = ta.adx(df["high"], df["low"], df["close"], 14)
        if adx is not None:
            df["ADX"] = adx["ADX_14"]

    # 3. H1 (Bias): EMA50
    elif tf == "1h":
        df["EMA50"] = ta.ema(df["close"], 50)

    # 4. M30 (Setup): Digunakan untuk structure swing (raw price)
    # Tidak butuh indikator berat, hanya price action.
    elif tf == "30m":
        pass 

    # 5. M15 (Execution): EMA20 untuk momentum (opsional), ATR untuk Risk
    elif tf == "15m":
        df["EMA20"] = ta.ema(df["close"], 20)
        df["ATR"] = ta.atr(df["high"], df["low"], df["close"], 14)

    df.dropna(inplace=True)
    return df

# ================================================================
# MARKET STRUCTURE (HH/HL Logic)
# ================================================================
def compute_trend_structure(df, window=20):
    """
    Mendeteksi Struktur HH/HL (Bullish) atau LH/LL (Bearish).
    Menggunakan Rolling Max/Min untuk mencari Swing Points lokal.
    """
    if df is None or len(df) < window * 2:
        return "NEUTRAL"

    # Cari Swing Highs & Lows (Window 10 kiri-kanan)
    highs = df['high'].rolling(window=10, center=True).max()
    lows = df['low'].rolling(window=10, center=True).min()
    
    # Ambil 2 titik swing terakhir yang valid (tidak NaN)
    # unique() digunakan untuk menghindari titik yang sama berulang saat rolling geser
    valid_highs = highs.dropna().unique()
    valid_lows = lows.dropna().unique()
    
    if len(valid_highs) < 2 or len(valid_lows) < 2:
        return "NEUTRAL"
    
    # Ambil 2 swing terakhir
    curr_high, prev_high = valid_highs[-1], valid_highs[-2]
    curr_low, prev_low = valid_lows[-1], valid_lows[-2]
    
    # Bullish: Higher High & Higher Low
    if curr_high > prev_high and curr_low > prev_low:
        return "LONG"
        
    # Bearish: Lower High & Lower Low
    elif curr_high < prev_high and curr_low < prev_low:
        return "SHORT"
        
    return "NEUTRAL"