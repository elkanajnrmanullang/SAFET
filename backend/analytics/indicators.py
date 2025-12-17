import pandas as pd
import pandas_ta as ta
import numpy as np
from backend.core.config import config

# 1. BASIC HELPERS
def compute_atr(df, length=14):
    try:
        if "ATR" in df.columns: return df["ATR"].iloc[-1]
        atr_series = ta.atr(df["high"], df["low"], df["close"], length)
        return float(atr_series.iloc[-1])
    except:
        return 0.0

def compute_volume_ma(df, length=20):
    return df["volume"].rolling(length).mean()

def compute_atr_sma(df, length=20):
    if "ATR" not in df.columns:
        df["ATR"] = ta.atr(df["high"], df["low"], df["close"], 14) 
    return df["ATR"].rolling(length).mean().iloc[-1]

def compute_avg_body(df, length=10):
    body = (df['close'] - df['open']).abs()
    return body.rolling(window=length).mean()

# 2. TIMEFRAME-BASED INDICATORS (Required by data.py)
def apply_indicators_by_tf(df, tf):
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
        df["RSI"] = ta.rsi(df["close"], 14)

    # 3. H1 (Bias): EMA50, ATR, RSI (for Volatility Gate)
    elif tf == "1h":
        df["EMA50"] = ta.ema(df["close"], 50)
        df["ATR"] = ta.atr(df["high"], df["low"], df["close"], 14)
        df["RSI"] = ta.rsi(df["close"], 14)

    # 4. M30 (Setup): Structure swing, butuh ATR untuk dynamic zone
    elif tf == "30m":
        df["ATR"] = ta.atr(df["high"], df["low"], df["close"], 14)

    # 5. M15 (Execution): ATR untuk Risk Management
    elif tf == "15m":
        df["ATR"] = ta.atr(df["high"], df["low"], df["close"], 14)

    df.dropna(inplace=True)
    return df

# 3. STRUCTURE & DIVERGENCE (Required by data.py)
def detect_rsi_divergence(df, direction):
    if df is None or len(df) < 50 or "RSI" not in df.columns:
        return False, "Insufficient Data/RSI"

    # Rolling window untuk swing point
    highs = df['high'].rolling(window=10, center=True).max()
    lows = df['low'].rolling(window=10, center=True).min()
    
    high_points = df[df['high'] == highs]['high'].dropna().drop_duplicates(keep='last')
    low_points = df[df['low'] == lows]['low'].dropna().drop_duplicates(keep='last')
    
    if len(high_points) < 2 or len(low_points) < 2:
        return False, "Need more swings"

    if direction == "LONG": 
        c_high, p_high = high_points.iloc[-1], high_points.iloc[-2]
        c_rsi = df.loc[high_points.index[-1], 'RSI']
        p_rsi = df.loc[high_points.index[-2], 'RSI']
        
        if c_high > p_high and c_rsi < p_rsi:
            return True, "Bearish Divergence (Price HH, RSI LH)"
            
    elif direction == "SHORT": 
        c_low, p_low = low_points.iloc[-1], low_points.iloc[-2]
        c_rsi = df.loc[low_points.index[-1], 'RSI']
        p_rsi = df.loc[low_points.index[-2], 'RSI']

        if c_low < p_low and c_rsi > p_rsi:
            return True, "Bullish Divergence (Price LL, RSI HL)"

    return False, "None"

def compute_trend_structure(df, adx_value):
    adx_val = float(adx_value) if adx_value else 0
    window_size = 10 if adx_val >= config.ADX_AGGRESSIVE_THRESHOLD else 20 # Adaptive

    if df is None or len(df) < window_size * 2:
        return "NEUTRAL", window_size

    highs = df['high'].rolling(window=10, center=True).max()
    lows = df['low'].rolling(window=10, center=True).min()
    
    df_recent = df.tail(window_size)
    valid_highs = sorted([h for i, h in df_recent['high'].items() if h == highs.get(i)], reverse=True)
    valid_lows = sorted([l for i, l in df_recent['low'].items() if l == lows.get(i)])

    if len(valid_highs) < 2 or len(valid_lows) < 2:
        return "NEUTRAL", window_size
    
    # Check Structure
    curr_h, prev_h = valid_highs[0], valid_highs[1]
    curr_l, prev_l = valid_lows[0], valid_lows[1]
    
    if curr_h > prev_h and curr_l > prev_l: return "LONG", window_size
    if curr_h < prev_h and curr_l < prev_l: return "SHORT", window_size
        
    return "NEUTRAL", window_size

# 4. OBJECTIVE SCORING LOGIC (New Requirements)
def calculate_snr_score(df, level, atr_m30):
    score = 0
    zone_width = atr_m30 * config.ATR_ZONE_WIDTH
    upper = level + zone_width
    lower = level - zone_width
    
    recent = df.tail(50)
    for i in range(len(recent)):
        row = recent.iloc[i]
        c_close, c_open = row['close'], row['open']
        c_high, c_low = row['high'], row['low']
        
        # Cek interaksi zona
        if (lower <= c_high <= upper) or (lower <= c_low <= upper):
            # Body Breakout
            if (c_close > upper and c_open < lower) or (c_close < lower and c_open > upper):
                score += config.SCORE_BODY_BREAKOUT
            # Bounce Body
            elif (c_high >= lower and c_close > c_open) or (c_low <= upper and c_close < c_open):
                score += config.SCORE_BOUNCE_BODY
            # Wick Rejection
            elif (c_high - max(c_open, c_close)) > (c_high - c_low) * 0.6:
                score += config.SCORE_WICK_REJECTION

    score += config.SCORE_FRESHNESS
    return score

def detect_weakening(df):
    if len(df) < 15: return False
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    avg_body = compute_avg_body(df, config.WEAKENING_LOOKBACK).iloc[-1]
    curr_body = abs(last['close'] - last['open'])
    prev_body = abs(prev['close'] - prev['open'])
    
    return (curr_body / (avg_body + 1e-9) < config.WEAKENING_RATIO) and (curr_body < prev_body)

def detect_fvg_zone(df, direction):
    if len(df) < 5: return None
    
    for i in range(len(df)-3, 0, -1):
        c0 = df.iloc[i]
        c2 = df.iloc[i+2]
        atr = c0.get('ATR', 0)
        
        if direction == "LONG":
            gap = c2['low'] - c0['high'] 
            if gap > (atr * config.FVG_MIN_SIZE_ATR):
                return {"top": c2['low'], "bottom": c0['high'], "type": "BULLISH_FVG"}
        elif direction == "SHORT":
            gap = c0['low'] - c2['high'] 
            if gap > (atr * config.FVG_MIN_SIZE_ATR):
                return {"top": c0['low'], "bottom": c2['high'], "type": "BEARISH_FVG"}
                
    return None