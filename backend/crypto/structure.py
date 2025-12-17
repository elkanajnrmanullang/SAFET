import numpy as np
import pandas as pd
from backend.core.config import config
from backend.analytics.indicators import calculate_snr_score, detect_weakening

# OBJEKTIF LIQUIDITY GRAB 
def detect_liquidity_grab(df, direction, timeframe="15m"):
    if len(df) < 50: return False, None
    
    atr = df['ATR'].iloc[-1]
    tolerance = atr * (0.2 if timeframe == "15m" else 0.4)
    last = df.iloc[-1]
    prev_candles = df.iloc[-30:-1] 
    found_liquidity = False
    liq_level = 0
    
    if direction == "LONG":
        for idx, row in prev_candles.iterrows():
            pass 
        
        swing_low = prev_candles['low'].min()
        if last['low'] < swing_low and last['close'] > swing_low:
            return True, swing_low
            
    elif direction == "SHORT":
        swing_high = prev_candles['high'].max()
        if last['high'] > swing_high and last['close'] < swing_high:
            return True, swing_high
            
    return False, None

# OBJEKTIF CHART PATTERN (Skenario 1 - Flag/Pennant/Double)
def detect_objective_pattern(df_h1):
    if len(df_h1) < 20: return "NONE"
    
    atr = df_h1['ATR'].iloc[-1]
    recent = df_h1.tail(15)
    
    # 1. Impulse Check 
    move_range = recent['high'].max() - recent['low'].min()
    if move_range < (1.5 * atr):
        return "NONE" 
        
    # 2. Consolidation Check 
    consolidation = df_h1.tail(5)
    cons_range = consolidation['high'].max() - consolidation['low'].min()
    
    if cons_range <= (0.8 * atr):
        first = recent.iloc[0]
        last = recent.iloc[-1]
        
        if last['close'] > first['open']: return "BULLISH_FLAG"
        if last['close'] < first['open']: return "BEARISH_FLAG"
        
    return "NONE"

# MARKET STRUCTURE ANALYZER (Main Helper)
def analyze_structure_context(df_m30, df_m15, df_h1):
    last_m15 = df_m15.iloc[-1]
    atr_m30 = df_m30['ATR'].iloc[-1] if 'ATR' in df_m30 else 0
    
    # 1. Trend H1
    ema50_h1 = df_h1['EMA50'].iloc[-1]
    trend_h1 = "UP" if df_h1['close'].iloc[-1] > ema50_h1 else "DOWN"
    
    # 2. SnR Scoring M30
    res_level = df_m30['high'].rolling(20).max().iloc[-1]
    sup_level = df_m30['low'].rolling(20).min().iloc[-1]
    snr_score_res = calculate_snr_score(df_m30, res_level, atr_m30)
    snr_score_sup = calculate_snr_score(df_m30, sup_level, atr_m30)
    
    snr_status = "WEAK"
    relevant_level = 0
    
    if trend_h1 == "UP":
        relevant_level = sup_level
        if snr_score_sup >= 7: snr_status = "STRONG"
        elif snr_score_sup >= 4: snr_status = "INTERMEDIATE"
    else: 
        relevant_level = res_level
        if snr_score_res >= 7: snr_status = "STRONG"
        elif snr_score_res >= 4: snr_status = "INTERMEDIATE"

    # 3. Weakening & Patterns
    is_weak = detect_weakening(df_m15)
    pattern_h1 = detect_objective_pattern(df_h1)
    
    return {
        "trend_h1": trend_h1,
        "snr_status": snr_status,
        "snr_level": relevant_level,
        "is_weakening": is_weak,
        "pattern_h1": pattern_h1
    }