import pandas as pd
import pandas_ta as ta
import numpy as np

# Import ADX threshold untuk penentuan Window
from backend.core.config import config # <-- IMPORT BARU

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

# [NEW] Calculate ATR SMA for H1 Volatility Check
def compute_atr_sma(df, length=20):
    """Menghitung Simple Moving Average dari ATR."""
    if "ATR" not in df.columns:
        # Asumsi ATR sudah dihitung (misal di apply_indicators_by_tf)
        df["ATR"] = ta.atr(df["high"], df["low"], df["close"], 14) 
    return df["ATR"].rolling(length).mean().iloc[-1]

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

    # 2. H4 (Anchor): EMA50, EMA200, ADX, RSI (for Divergence Check)
    if tf == "4h":
        df["EMA50"] = ta.ema(df["close"], 50)
        df["EMA200"] = ta.ema(df["close"], 200)
        adx = ta.adx(df["high"], df["low"], df["close"], 14)
        if adx is not None:
            df["ADX"] = adx["ADX_14"]
        df["RSI"] = ta.rsi(df["close"], 14) # <-- NEW

    # 3. H1 (Bias): EMA50, ATR, RSI (for Volatility Gate & Divergence Check)
    elif tf == "1h":
        df["EMA50"] = ta.ema(df["close"], 50)
        df["ATR"] = ta.atr(df["high"], df["low"], df["close"], 14) # <-- NEW
        df["RSI"] = ta.rsi(df["close"], 14) # <-- NEW

    # 4. M30 (Setup): Digunakan untuk structure swing (raw price)
    elif tf == "30m":
        pass 

    # 5. M15 (Execution): EMA20 untuk momentum (opsional), ATR untuk Risk
    elif tf == "15m":
        df["EMA20"] = ta.ema(df["close"], 20)
        df["ATR"] = ta.atr(df["high"], df["low"], df["close"], 14)

    df.dropna(inplace=True)
    return df

# [NEW FUNCTION] Check H4 Exhaustion (RSI Divergence)
def detect_rsi_divergence(df, direction):
    """
    Mendeteksi Divergence (Higher High Price, Lower High RSI dsb.)
    Hanya cek dua swing point terakhir yang unik.
    """
    if df is None or len(df) < 50 or "RSI" not in df.columns:
        return False, "Insufficient Data/RSI"

    # Gunakan rolling window kecil untuk menemukan titik swing lokal
    highs = df['high'].rolling(window=10, center=True).max()
    lows = df['low'].rolling(window=10, center=True).min()
    
    # Filter data point di mana High/Low sama dengan rolling max/min (titik swing)
    high_points = df[df['high'] == highs]['high'].dropna().drop_duplicates(keep='last')
    low_points = df[df['low'] == lows]['low'].dropna().drop_duplicates(keep='last')
    
    if len(high_points) < 2 or len(low_points) < 2:
        return False, "Need more than 2 swings"

    if direction == "LONG":
        # Bearish Divergence (Higher High Price, Lower High RSI)
        current_high = high_points.iloc[-1]
        previous_high = high_points.iloc[-2]
        
        # Cari RSI pada index harga swing tersebut
        current_rsi = df[df['high'] == current_high]['RSI'].iloc[-1]
        previous_rsi = df[df['high'] == previous_high]['RSI'].iloc[-1]
        
        # Cek Divergence
        is_higher_high_price = current_high > previous_high
        is_lower_high_rsi = current_rsi < previous_rsi

        if is_higher_high_price and is_lower_high_rsi:
            return True, "H4 Bearish Divergence (Price HH, RSI LH)"
            
    elif direction == "SHORT":
        # Bullish Divergence (Lower Low Price, Higher Low RSI)
        current_low = low_points.iloc[-1]
        previous_low = low_points.iloc[-2]

        # Cari RSI pada index harga swing tersebut
        current_rsi = df[df['low'] == current_low]['RSI'].iloc[-1]
        previous_rsi = df[df['low'] == previous_low]['RSI'].iloc[-1]

        # Cek Divergence
        is_lower_low_price = current_low < previous_low
        is_higher_low_rsi = current_rsi > previous_rsi

        if is_lower_low_price and is_higher_low_rsi:
            return True, "H4 Bullish Divergence (Price LL, RSI HL)"

    return False, "No Divergence Detected"


# ================================================================
# MARKET STRUCTURE (HH/HL Logic) - Adaptive Lookback Window
# ================================================================
def compute_trend_structure(df, adx_value): # <-- ADD ADX INPUT
    """
    Mendeteksi Struktur HH/HL (Bullish) atau LH/LL (Bearish) dengan Adaptive Lookback Window.
    """
    
    # 1. Tentukan Window Adaptif
    adx_val = float(adx_value) if adx_value else 0
    
    if adx_val >= config.ADX_AGGRESSIVE_THRESHOLD:
        window_size = 10 # Mode Agresif (ADX > 30)
    elif adx_val >= config.ADX_NORMAL_THRESHOLD:
        window_size = 20 # Mode Standar (ADX 20-30)
    else:
        # Jika ADX < 20, Filter akan memblokir di data.py, kita kembalikan default.
        return "NEUTRAL", 20 

    if df is None or len(df) < window_size * 2:
        return "NEUTRAL", window_size

    # Cari Swing Highs & Lows (Window 10 kiri-kanan untuk menentukan titik swing)
    highs = df['high'].rolling(window=10, center=True).max()
    lows = df['low'].rolling(window=10, center=True).min()
    
    # Filter data hanya pada N candle terakhir (sesuai Adaptive Window)
    df_recent = df.tail(window_size)
    
    # Ambil titik swing yang berada di dalam df_recent
    valid_highs_set = set()
    valid_lows_set = set()
    
    # Cari indeks di df_recent yang sesuai dengan swing point
    for index in df_recent.index:
        # Check jika candle high/low sama dengan rolling max/min-nya (swing point)
        if df_recent.loc[index, 'high'] == highs.loc[index]:
            valid_highs_set.add(df_recent.loc[index, 'high'])
        if df_recent.loc[index, 'low'] == lows.loc[index]:
            valid_lows_set.add(df_recent.loc[index, 'low'])
            
    valid_highs = sorted(list(valid_highs_set), reverse=True) # Sort dari terbesar (Current High)
    valid_lows = sorted(list(valid_lows_set))                 # Sort dari terkecil (Current Low)

    # Fallback jika tidak ketemu 2 swing point yang valid dalam periode adaptif
    if len(valid_highs) < 2 or len(valid_lows) < 2:
        # Ambil 2 nilai max/min saja dari window terakhir
        valid_highs = df_recent['high'].nlargest(2).unique()
        valid_lows = df_recent['low'].nsmallest(2).unique()
        
    if len(valid_highs) < 2 or len(valid_lows) < 2:
        return "NEUTRAL", window_size
    
    # Ambil 2 swing terakhir (High: 2 tertinggi, Low: 2 terendah)
    curr_high, prev_high = valid_highs[0], valid_highs[1]
    curr_low, prev_low = valid_lows[0], valid_lows[1]
    
    # Bullish: Higher High & Higher Low
    if curr_high > prev_high and curr_low > prev_low:
        return "LONG", window_size
        
    # Bearish: Lower High & Lower Low
    elif curr_high < prev_high and curr_low < prev_low:
        return "SHORT", window_size
        
    return "NEUTRAL", window_size