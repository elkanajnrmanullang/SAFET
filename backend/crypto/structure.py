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
    recent_vol = df['volume'].tail(lookback).values
    if len(recent_vol) < 2: return "NEUTRAL"
    slope = np.polyfit(range(len(recent_vol)), recent_vol, 1)[0]
    current_vol = recent_vol[-1]
    avg_vol = df['volume'].tail(20).mean()
    is_increasing = slope > 0 and current_vol > avg_vol
    return "INCREASING" if is_increasing else "DECREASING"

def detect_m15_execution(df_m15, direction):
    """
    [DEFAULT STRATEGY] Analisa M15 Advanced:
    - Breakout + High Vol (Assault Trigger)
    - Bounce/Pullback + Low Vol (Sniper/Guerrilla Trigger)
    
    PENTING: Selalu return 'levels' lokal M15 untuk Tier 2 & 3.
    """
    if df_m15 is None or len(df_m15) < 30:
        return {
            "valid": False, 
            "reason": "M15 Data Insufficient", 
            "levels": {"support": 0, "resistance": 0}
        }

    last = df_m15.iloc[-1]
    
    # 1. Identifikasi Level Kunci M15 (Lokal)
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
        # A. Breakout Resistance (Penerusan - Cocok untuk Assault)
        if last['close'] > res and (vol_trend == "INCREASING" or vol_spike):
            valid_trigger = True
            detail_msg = "🔥 Breakout Resistance + High Vol"
            
        # B. Bounce at Support/Pullback (Pantulan - Cocok untuk Sniper/Guerrilla)
        # Toleransi area 0.5% dari support
        elif abs(last['low'] - sup) / sup < 0.005: 
            if lower_wick > body: 
                valid_trigger = True
                detail_msg = "🪤 Bounce Support (Pinbar)"
            elif is_bullish and vol_trend == "DECREASING":
                valid_trigger = True
                detail_msg = "📉 Pullback Entry (Vol Dried Up)"
        
        # C. Impulse Candle (Backup untuk Assault jika tidak ada level struktur jelas)
        elif vol_spike and is_bullish and body > (upper_wick + lower_wick):
            valid_trigger = True
            detail_msg = "🚀 Momentum Impulse (Mid-Range)"

    # === LOGIC UNTUK POSISI SHORT ===
    elif direction == "SHORT":
        # A. Breakdown Support (Penerusan - Cocok untuk Assault)
        if last['close'] < sup and (vol_trend == "INCREASING" or vol_spike):
            valid_trigger = True
            detail_msg = "🔥 Breakdown Support + High Vol"
            
        # B. Rejection at Resistance (Pantulan - Cocok untuk Sniper/Guerrilla)
        elif abs(last['high'] - res) / res < 0.005:
            if upper_wick > body: 
                valid_trigger = True
                detail_msg = "🪤 Reject Resistance (Pinbar)"
            elif not is_bullish and vol_trend == "DECREASING":
                valid_trigger = True
                detail_msg = "📉 Pullback Entry (Vol Dried Up)"

        # C. Impulse Candle (Backup untuk Assault)
        elif vol_spike and not is_bullish and body > (upper_wick + lower_wick):
             valid_trigger = True
             detail_msg = "🚀 Momentum Impulse (Mid-Range)"

    # --- RETURN RESULT WITH LEVELS ---
    # Kita selalu return levels (sup/res) lokal M15 meskipun valid=False
    # Agar Engine bisa pakai data ini jika diperlukan untuk Risk Calculation
    result_data = {
        "valid": valid_trigger, 
        "reason": detail_msg if valid_trigger else "No Valid M15 Trigger",
        "detail": detail_msg,
        "levels": {"support": sup, "resistance": res}  # <--- DATA VITAL UNTUK TIER 2 & 3
    }

    return result_data

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
    Analisa M30 (Zone Filter & Liquidity):
    1. Identifikasi Swing High/Low.
    2. Deteksi Sweep (False Break).
    3. Validasi respon area.
    """
    if df_m30 is None or len(df_m30) < 50:
        return {"valid": False, "reason": "M30 Data Insufficient"}

    # Ambil Swing Points (Fractal sederhana)
    # Window 5 kiri, 5 kanan untuk swing valid
    df_m30['swing_high'] = df_m30['high'].rolling(window=10, center=True).max()
    df_m30['swing_low'] = df_m30['low'].rolling(window=10, center=True).min()
    
    last = df_m30.iloc[-1]
    prev_candles = df_m30.tail(5).to_dict('records') # Cek 5 candle terakhir utk sweep
    
    valid_setup = False
    detail_msg = ""
    
    # Cari Swing Valid Terakhir (Liquidity Pool)
    # Kita cari nilai swing high/low yg valid (bukan NaN) terdekat
    last_valid_high = df_m30['swing_high'].dropna().iloc[-1] if not df_m30['swing_high'].dropna().empty else df_m30['high'].max()
    last_valid_low = df_m30['swing_low'].dropna().iloc[-1] if not df_m30['swing_low'].dropna().empty else df_m30['low'].min()

    # --- LOGIC LIQUIDITY SWEEP ---
    # Syarat: Ekor tembus level, tapi Close balik ke dalam
    
    if direction == "LONG":
        # Cari Sweep di Low (Stop Hunt Buyer / Trap Seller)
        for c in prev_candles:
            # Low candle lebih rendah dari Swing Low sebelumnya
            if c['low'] < last_valid_low:
                # Tapi Close-nya kembali di atas Swing Low (Rejection)
                if c['close'] > last_valid_low:
                    valid_setup = True
                    detail_msg = "M30 Liquidity Sweep (Bullish Rejection)"
                    break
                    
    elif direction == "SHORT":
        # Cari Sweep di High (Stop Hunt Seller / Trap Buyer)
        for c in prev_candles:
            # High candle lebih tinggi dari Swing High sebelumnya
            if c['high'] > last_valid_high:
                # Tapi Close-nya kembali di bawah Swing High (Rejection)
                if c['close'] < last_valid_high:
                    valid_setup = True
                    detail_msg = "M30 Liquidity Sweep (Bearish Rejection)"
                    break
    
    # Fallback: Jika harga berada di "Zone Penting" tanpa sweep ekstrim (Retest biasa)
    if not valid_setup:
        # Simple Zone Filter: Harga mendekati key level dalam toleransi 0.5%
        if direction == "LONG" and abs(last['close'] - last_valid_low) / last_valid_low < 0.005:
             valid_setup = True
             detail_msg = "M30 Support Retest (In Zone)"
        elif direction == "SHORT" and abs(last['close'] - last_valid_high) / last_valid_high < 0.005:
             valid_setup = True
             detail_msg = "M30 Resistance Retest (In Zone)"

    if valid_setup:
        return {"valid": True, "detail": detail_msg, "levels": {"support": last_valid_low, "resistance": last_valid_high}}
    
    return {"valid": False, "reason": "No M30 Liquidity/Zone Setup Found"}


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