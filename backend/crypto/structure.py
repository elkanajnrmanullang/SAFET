"""
Advanced Market Structure Detector
----------------------------------
Handles M15 Execution with Price Action logic:
1. Detects Local Support/Resistance.
2. Analyzes Volume Behavior (Increasing vs Decreasing).
3. Identifies Rejection (Bounce) vs Continuation (Breakout).

ALSO INCLUDES:
- Basic Liquidity Sweep Detector (Strategy 2)
- Momentum Impulse Detector (Strategy 2)
"""

import numpy as np
import pandas as pd

# ==============================================================================
# STRATEGY 1: ADVANCED (Support/Resistance + Volume Analysis)
# ==============================================================================

def _get_local_sr(df, window=20):
    """Mencari Support & Resistance Lokal berdasarkan Swing High/Low terakhir"""
    highs = df['high'].rolling(window=5, center=True).max()
    lows = df['low'].rolling(window=5, center=True).min()
    
    # Ambil level valid terakhir
    res_level = highs.dropna().iloc[-1] if not highs.dropna().empty else df['high'].max()
    sup_level = lows.dropna().iloc[-1] if not lows.dropna().empty else df['low'].min()
    
    return res_level, sup_level

def _analyze_volume_trend(df, lookback=5):
    """
    Menganalisa apakah volume sedang Meningkat (Strong) atau Melemah (Weak)
    dalam n-candle terakhir.
    """
    recent_vol = df['volume'].tail(lookback).values
    # Hitung rata-rata perubahan (slope)
    if len(recent_vol) < 2: return "NEUTRAL"
    
    slope = np.polyfit(range(len(recent_vol)), recent_vol, 1)[0]
    
    current_vol = recent_vol[-1]
    avg_vol = df['volume'].tail(20).mean()
    
    is_increasing = slope > 0 and current_vol > avg_vol
    is_decreasing = slope < 0 or current_vol < avg_vol
    
    return "INCREASING" if is_increasing else "DECREASING"

def detect_m15_execution(df_m15, direction):
    """
    [DEFAULT STRATEGY] Analisa M15 Advanced:
    - Breakout + High Vol
    - Bounce/Pullback + Low Vol
    """
    if df_m15 is None or len(df_m15) < 30:
        return {"valid": False, "reason": "M15 Data Insufficient"}

    last = df_m15.iloc[-1]
    
    # 1. Identifikasi Level Kunci
    res, sup = _get_local_sr(df_m15)
    
    # 2. Analisa Volume
    vol_trend = _analyze_volume_trend(df_m15)
    vol_spike = last['volume'] > (df_m15['volume'].rolling(20).mean().iloc[-1] * 1.2)
    
    # 3. Analisa Candle Shape
    body = abs(last['close'] - last['open'])
    upper_wick = last['high'] - max(last['close'], last['open'])
    lower_wick = min(last['close'], last['open']) - last['low']
    is_bullish = last['close'] > last['open']
    
    detail_msg = ""
    valid_trigger = False
    
    # === LOGIC UNTUK POSISI LONG ===
    if direction == "LONG":
        # A. Breakout Resistance (Penerusan)
        if last['close'] > res and (vol_trend == "INCREASING" or vol_spike):
            valid_trigger = True
            detail_msg = "🔥 Breakout Resistance + High Vol"
            
        # B. Bounce at Support/Pullback (Pantulan)
        elif abs(last['low'] - sup) / sup < 0.005: 
            if lower_wick > body: 
                valid_trigger = True
                detail_msg = "🪃 Bounce Support (Pinbar)"
            elif is_bullish and vol_trend == "DECREASING":
                valid_trigger = True
                detail_msg = "📉 Pullback Entry (Vol Dried Up)"

    # === LOGIC UNTUK POSISI SHORT ===
    elif direction == "SHORT":
        # A. Breakdown Support (Penerusan)
        if last['close'] < sup and (vol_trend == "INCREASING" or vol_spike):
            valid_trigger = True
            detail_msg = "🔥 Breakdown Support + High Vol"
            
        # B. Rejection at Resistance (Pantulan)
        elif abs(last['high'] - res) / res < 0.005:
            if upper_wick > body: 
                valid_trigger = True
                detail_msg = "🪃 Reject Resistance (Pinbar)"
            elif not is_bullish and vol_trend == "DECREASING":
                valid_trigger = True
                detail_msg = "📉 Pullback Entry (Vol Dried Up)"

    # Default Impulse Check (Fallback)
    if not valid_trigger:
        if vol_spike and body > (upper_wick + lower_wick):
             if (direction == "LONG" and is_bullish) or (direction == "SHORT" and not is_bullish):
                 valid_trigger = True
                 detail_msg = "🚀 Momentum Impulse (Mid-Range)"

    if not valid_trigger:
        return {"valid": False, "reason": "No Valid Setup (Wait for Breakout or Bounce)"}
        
    return {"valid": True, "detail": detail_msg}


# ==============================================================================
# STRATEGY 2: BASIC / ALTERNATIVE (Liquidity Sweep & Simple Impulse)
# ==============================================================================

def _is_sweep(candle, neighbor_high, neighbor_low, direction):
    """
    Detect liquidity sweep:
    - Bearish Sweep (Short): High candle menembus prev High, tapi Close di bawahnya.
    - Bullish Sweep (Long): Low candle menembus prev Low, tapi Close di atasnya.
    """
    open_c, close_c = candle["open"], candle["close"]
    high_c, low_c = candle["high"], candle["low"]
    
    if direction == "LONG":
        # Sweep Low: Ekor bawah panjang mengambil likuiditas low tetangga
        if low_c < neighbor_low and min(open_c, close_c) > neighbor_low:
            return True
    elif direction == "SHORT":
        # Sweep High: Ekor atas panjang mengambil likuiditas high tetangga
        if high_c > neighbor_high and max(open_c, close_c) < neighbor_high:
            return True
    return False

def detect_liquidity_setup(df_m30, direction):
    """
    Analisa M30 (Strategy 2):
    1. Cari Swing High/Low terakhir (Liquidity Pool).
    2. Cek apakah ada candle (terakhir 1-3) yang melakukan 'Sweep'.
    """
    if df_m30 is None or len(df_m30) < 20:
        return {"valid": False, "reason": "M30 Data Insufficient"}

    # Simple swing detection (3 candles fractal)
    last_highs = df_m30["high"].rolling(3, center=True).max()
    last_lows = df_m30["low"].rolling(3, center=True).min()
    
    # Ambil swing point yang valid (bukan NaN)
    valid_high_val = last_highs.dropna().iloc[-5] if len(last_highs.dropna()) > 5 else df_m30["high"].max()
    valid_low_val = last_lows.dropna().iloc[-5] if len(last_lows.dropna()) > 5 else df_m30["low"].min()

    # Cek Sweep di 3 candle terakhir
    swept = False
    recent_candles = df_m30.tail(3).to_dict('records')
    
    for candle in recent_candles:
        if _is_sweep(candle, valid_high_val, valid_low_val, direction):
            swept = True
            break
            
    # Sesuai rule: M30 Liquidity Swept + Setup Confirmed (Kita anggap sweep = setup trigger)
    if swept:
        return {"valid": True, "detail": "Liquidity Sweep Detected"}
    
    return {"valid": False, "reason": "No M30 Liquidity Sweep Found"}


def detect_m15_execution_basic(df_m15, direction):
    """
    Analisa M15 (Execution - Strategy 2 Basic):
    1. Candle Impulsif searah.
    2. Volume > Vol_MA20.
    
    *Note: Fungsi ini direname dari 'detect_m15_execution' agar tidak bentrok
    dengan fungsi Advanced di atas.*
    """
    if df_m15 is None or len(df_m15) < 20:
        return {"valid": False, "reason": "M15 Data Insufficient"}

    last = df_m15.iloc[-1]
    
    # 1. Volume Confirmation
    vol_valid = last["volume"] > last.get("Vol_MA20", 0)
    
    # 2. Momentum / Impulse Check
    is_bullish = last["close"] > last["open"]
    body = abs(last["close"] - last["open"])
    wick_total = (last["high"] - last["low"]) - body
    is_impulse = body > wick_total # Body lebih besar dari ekor (strong candle)
    
    momentum_valid = False
    if direction == "LONG" and is_bullish and is_impulse:
        momentum_valid = True
    elif direction == "SHORT" and not is_bullish and is_impulse:
        momentum_valid = True
        
    if not momentum_valid:
        return {"valid": False, "reason": "M15 Low Momentum / Indecision Candle"}
        
    if not vol_valid:
        return {"valid": False, "reason": "M15 Low Volume (< Avg)"}
        
    return {"valid": True, "detail": "Impulse + Vol Confirmed"}