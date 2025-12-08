"""
Advanced Market Structure Detector
----------------------------------
Handles M15 Execution with Price Action logic:
1. Detects Local Support/Resistance.
2. Analyzes Volume Behavior (Increasing vs Decreasing).
3. Identifies Rejection (Bounce) vs Continuation (Breakout).
"""

import numpy as np
import pandas as pd
from backend.core.config import config # <-- NEW IMPORT

# ==============================================================================
# STRUCTURE HELPER (Adjusted _get_local_sr window to 5 for fast local levels)
# ==============================================================================
def _get_local_sr(df, window=5): 
    """Mencari Support & Resistance Lokal berdasarkan Swing High/Low terakhir"""
    highs = df['high'].rolling(window=window, center=True).max()
    lows = df['low'].rolling(window=window, center=True).min()
    
    # Ambil level valid terakhir
    res_level = highs.dropna().iloc[-1] if not highs.dropna().empty else df['high'].max()
    sup_level = lows.dropna().iloc[-1] if not lows.dropna().empty else df['low'].min()
    
    return res_level, sup_level

def _analyze_volume_trend(df, lookback=5):
    recent_vol = df['volume'].tail(lookback).values
    if len(recent_vol) < 2: return "NEUTRAL"
    slope = np.polyfit(range(len(recent_vol)), recent_vol, 1)[0]
    current_vol = recent_vol[-1]
    avg_vol = df['volume'].tail(20).mean()
    is_increasing = slope > 0 and current_vol > avg_vol
    return "INCREASING" if is_increasing else "DECREASING"

# [NEW HELPER] FVG Check (Skenario C)
def _check_fvg(df, direction):
    """Cek apakah candle saat ini mengisi FVG di 3 candle sebelumnya (C3, C2, C1)."""
    if len(df) < 4: return False
    
    c1, c2, c3 = df.iloc[-1], df.iloc[-2], df.iloc[-3]
    
    # Pengecekan FVG Bullish
    if direction == "LONG":
        # FVG Terbentuk jika Low C3 > High C2
        if c3['low'] > c2['high']:
            fvg_low = c2['high']
            fvg_high = c3['low']
            # Candle saat ini harus memiliki low di dalam range FVG dan close di atas FVG low.
            if c1['low'] < fvg_high and c1['close'] > fvg_low:
                 return True
    
    # Pengecekan FVG Bearish
    if direction == "SHORT":
        # FVG Terbentuk jika High C3 < Low C2
        if c3['high'] < c2['low']:
            fvg_low = c3['high']
            fvg_high = c2['low']
            # Candle saat ini harus memiliki high di dalam range FVG dan close di bawah FVG high.
            if c1['high'] > fvg_low and c1['close'] < fvg_high:
                 return True

    return False

# ==============================================================================
# M30 SETUP: LIQUIDITY & ZONE (Tier 1 Check)
# ==============================================================================

def _get_swing_grade(last_valid_highs: pd.Series, last_valid_lows: pd.Series):
    """
    Menentukan Grade Swing Point (Grade A = Equal High/Low)
    """
    if len(last_valid_highs) < 3 or len(last_valid_lows) < 3:
        return "Grade B (Clean Swing)"
        
    # Ambil 2 swing terakhir yang valid
    h1, h2 = last_valid_highs.iloc[-1], last_valid_highs.iloc[-2]
    l1, l2 = last_valid_lows.iloc[-1], last_valid_lows.iloc[-2]
    
    # Grade A (Equal Highs/Lows) - Toleransi 0.05%
    is_equal_high = abs(h1 - h2) / h1 < 0.0005
    is_equal_low = abs(l1 - l2) / l1 < 0.0005
    
    if is_equal_high or is_equal_low:
        return "Grade A (Equal High/Low)"
    
    return "Grade B (Clean Swing)"


def detect_liquidity_setup(df_m30, direction):
    """
    Analisa M30 (Zone Filter & Liquidity) - Update untuk Grading & Sweep 2-Step.
    """
    if df_m30 is None or len(df_m30) < 50:
        return {"valid": False, "reason": "M30 Data Insufficient", "levels": {}}

    # Gunakan window kecil untuk Swing Point agar lebih sensitif
    highs_rolling = df_m30['high'].rolling(window=10, center=True).max()
    lows_rolling = df_m30['low'].rolling(window=10, center=True).min()
    
    df_m30['swing_high'] = highs_rolling
    df_m30['swing_low'] = lows_rolling
    
    last = df_m30.iloc[-1]
    prev_candle = df_m30.iloc[-2]
    
    # Cari Swing Valid Terakhir (Liquidity Pool)
    last_valid_highs = df_m30['swing_high'].tail(50).dropna().drop_duplicates(keep='last')
    last_valid_lows = df_m30['swing_low'].tail(50).dropna().drop_duplicates(keep='last')

    if len(last_valid_highs) < 1 or len(last_valid_lows) < 1:
        # Fallback to simple max/min
        last_valid_high = df_m30['high'].tail(20).max()
        last_valid_low = df_m30['low'].tail(20).min()
    else:
        last_valid_high = last_valid_highs.iloc[-1]
        last_valid_low = last_valid_lows.iloc[-1]
    
    levels = {"support": last_valid_low, "resistance": last_valid_high}
    detail_msg = ""
    valid_setup = False
    
    # --- 1. Grading Swing Point (Optional Context) ---
    swing_grade = _get_swing_grade(last_valid_highs, last_valid_lows)
    
    # --- 2. Liquidity Sweep (Trap Detection - 2 Step) ---
    
    if direction == "LONG":
        # Bullish Sweep: Sweep Low
        # Step 1: Prev Candle Low tembus Swing Low, tapi Close > Swing Low
        is_sweep_candle = prev_candle['low'] < last_valid_low and prev_candle['close'] > last_valid_low
        
        # Step 2: Last Candle Close > Prev Candle Close (Micro-Displacement)
        is_micro_displacement = is_sweep_candle and last['close'] > prev_candle['close'] 
        
        if is_micro_displacement:
            valid_setup = True
            detail_msg = f"M30 Liquidity Sweep (Bullish Rejection) | {swing_grade} & Micro-Disp"
            
    elif direction == "SHORT":
        # Bearish Sweep: Sweep High
        # Step 1: Prev Candle High tembus Swing High, tapi Close < Swing High
        is_sweep_candle = prev_candle['high'] > last_valid_high and prev_candle['close'] < last_valid_high
        
        # Step 2: Last Candle Close < Prev Candle Close (Micro-Displacement)
        is_micro_displacement = is_sweep_candle and last['close'] < prev_candle['close']
        
        if is_micro_displacement:
            valid_setup = True
            detail_msg = f"M30 Liquidity Sweep (Bearish Rejection) | {swing_grade} & Micro-Disp"

    # --- 3. Fallback: Respon Zona (Tier 1/3) ---
    if not valid_setup:
        # Cek apakah harga Close saat ini berada di "Zone Penting" (toleransi 0.5%)
        close_price = last['close']
        if direction == "LONG" and abs(close_price - last_valid_low) / last_valid_low < 0.005:
             valid_setup = True
             detail_msg = "M30 Support Retest (In Zone)"
        elif direction == "SHORT" and abs(close_price - last_valid_high) / last_valid_high < 0.005:
             valid_setup = True
             detail_msg = "M30 Resistance Retest (In Zone)"

    if valid_setup:
        return {"valid": True, "detail": detail_msg, "levels": levels}
    
    return {"valid": False, "reason": "No M30 Liquidity/Zone Setup Found", "levels": levels}

# ==============================================================================
# M15 EXECUTION: SCENARIO A/B/C (Wajib untuk semua Tier)
# ==============================================================================

def detect_m15_execution(df_m15, direction, volatility_status="NORMAL"):
    """
    Analisa M15 Advanced - Implementasi Skenario A/B/C (Execution Trigger).
    """
    if df_m15 is None or len(df_m15) < 30:
        return {
            "valid": False, 
            "reason": "M15 Data Insufficient", 
            "levels": {"support": 0, "resistance": 0}
        }

    last = df_m15.iloc[-1]
    res, sup = _get_local_sr(df_m15, window=10) # Window 10 untuk level eksekusi
    vol_trend = _analyze_volume_trend(df_m15)
    
    # Candle metrics
    body = abs(last['close'] - last['open'])
    upper_wick = last['high'] - max(last['close'], last['open'])
    lower_wick = min(last['close'], last['open']) - last['low']
    is_bullish = last['close'] > last['open']
    
    # Volume metrics
    vol_spike = last['volume'] > (df_m15['volume'].rolling(20).mean().iloc[-1] * 1.5) # Vol > 1.5x Avg
    is_marubozu = body > (last['high'] - last['low']) * 0.7 # Body > 70% dari Total Range
    
    levels = {"support": sup, "resistance": res}
    
    # --- 1. Skenario C: Institutional Impulse (Marubozu + Vol + FVG Check) ---
    if vol_spike and is_marubozu and ((direction == "LONG" and is_bullish) or (direction == "SHORT" and not is_bullish)):
        is_fvg_filled = _check_fvg(df_m15.tail(4), direction) 
        detail_msg = f"🚀 Impulse Marubozu + Vol Spike {'(FVG Retest)' if is_fvg_filled else ''}"
        return {"valid": True, "reason": detail_msg, "detail": detail_msg, "levels": levels}


    # --- 2. Skenario B: Structural Bounce (Pinbar Valid & Pullback Vol Dried Up) ---
    # Toleransi area 0.5% dari level
    is_near_sup = abs(last['low'] - sup) / sup < 0.005
    is_near_res = abs(last['high'] - res) / res < 0.005
    
    if direction == "LONG" and is_near_sup:
        # Pola: Pinbar Valid (Ekor bawah > 2x Body)
        if lower_wick > body * 2:
            detail_msg = "🪤 Structural Bounce (Pinbar Valid)"
            return {"valid": True, "reason": detail_msg, "detail": detail_msg, "levels": levels}
        # Skenario B - Pullback/Retest: Candle Bullish kecil di support + Volume kering
        elif is_bullish and vol_trend == "DECREASING" and body > 0:
             detail_msg = "📉 Pullback Entry (Vol Dried Up)"
             return {"valid": True, "reason": detail_msg, "detail": detail_msg, "levels": levels}
        
    if direction == "SHORT" and is_near_res:
        # Pola: Pinbar Valid (Ekor atas > 2x Body)
        if upper_wick > body * 2:
            detail_msg = "🪤 Structural Rejection (Pinbar Valid)"
            return {"valid": True, "reason": detail_msg, "detail": detail_msg, "levels": levels}
        # Skenario B - Pullback/Retest: Candle Bearish kecil di resistance + Volume kering
        elif not is_bullish and vol_trend == "DECREASING" and body > 0:
             detail_msg = "📉 Pullback Entry (Vol Dried Up)"
             return {"valid": True, "reason": detail_msg, "detail": detail_msg, "levels": levels}


    # --- 3. Skenario A: Adaptive Breakout / Momentum Blast (Vol Confirmed) ---
    
    if direction == "LONG" and last['close'] > res:
        if vol_trend == "INCREASING" or vol_spike:
            detail_msg = "🔥 Adaptive Breakout (Vol Confirmed)"
            return {"valid": True, "reason": detail_msg, "detail": detail_msg, "levels": levels}
    
    if direction == "SHORT" and last['close'] < sup:
        if vol_trend == "INCREASING" or vol_spike:
            detail_msg = "🔥 Adaptive Breakdown (Vol Confirmed)"
            return {"valid": True, "reason": detail_msg, "detail": detail_msg, "levels": levels}
        

    # --- NO VALID TRIGGER ---
    detail_msg = f"No Valid M15 Trigger (Scenarios A/B/C Failed)"
    return {
        "valid": False, 
        "reason": detail_msg,
        "detail": detail_msg,
        "levels": levels
    }