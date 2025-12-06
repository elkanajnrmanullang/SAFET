"""
Mini CHOCH / BOS / Liquidity Detector
-------------------------------------
Handles M30 (Setup/Liquidity) and M15 (Execution) logic.
"""

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
    Analisa M30:
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
    
    # Relaxed rule: Jika tidak ada sweep, cek apakah harga Reclaim VWAP/EMA?
    # Untuk strictness sesuai prompt, kita return False jika tidak ada liquidity event
    return {"valid": False, "reason": "No M30 Liquidity Sweep Found"}


def detect_m15_execution(df_m15, direction):
    """
    Analisa M15 (Execution):
    1. Candle Impulsif searah.
    2. Volume > Vol_MA20.
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