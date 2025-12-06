import ccxt
import pandas as pd
import pandas_ta as ta
import numpy as np

from backend.analytics.indicators import (
    apply_indicators_by_tf,
    compute_atr,
    compute_trend_structure
)

# ================================================================
#  CONNECTION
# ================================================================
def get_exchange():
    return ccxt.binance({
        "enableRateLimit": True,
        "options": {"defaultType": "future"}
    })

def fetch_market_data(symbol, timeframe, limit=500):
    exc = get_exchange()
    try:
        # Fix symbol formatting safe guard
        safe_symbol = symbol.replace("USDT", "/USDT") if "/" not in symbol else symbol
        
        ohlcv = exc.fetch_ohlcv(safe_symbol, timeframe, limit=limit)
    except Exception as e:
        print(f"FETCH ERROR ({timeframe}):", e)
        return None

    if not ohlcv:
        return None

    df = pd.DataFrame(
        ohlcv,
        columns=["timestamp", "open", "high", "low", "close", "volume"]
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df

# ================================================================
#  INDICATOR WRAPPER
# ================================================================
def apply_indicators(df, tf):
    if df is None or df.empty:
        return None
    return apply_indicators_by_tf(df, tf)

# ================================================================
#  1. H4 ANALYZER (ANCHOR)
# ================================================================
def detect_trend_h4(df):
    """
    Rules:
    - EMA50 > EMA200 = BULLISH
    - EMA50 < EMA200 = BEARISH
    - ADX >= 20 -> Valid Trend
    """
    if df is None or len(df) < 200:
        return {"valid": False, "direction": "NEUTRAL", "adx": 0}

    last = df.iloc[-1]
    adx_val = last.get("ADX", 0)
    
    # 1. Determine Direction
    direction = "NEUTRAL"
    if last["EMA50"] > last["EMA200"]:
        direction = "LONG"
    elif last["EMA50"] < last["EMA200"]:
        direction = "SHORT"
        
    # 2. Validate Strength
    valid = False
    if direction != "NEUTRAL" and adx_val >= 20:
        valid = True
    
    return {
        "valid": valid, 
        "direction": direction, 
        "adx": float(adx_val),
        "reason": f"H4 EMA Alignment ({direction}), ADX={adx_val:.2f}"
    }

# ================================================================
#  2. H1 ANALYZER (BIAS)
# ================================================================
def detect_bias_h1(df, h4_direction):
    """
    Rules:
    - Bias valid jika harga aligned dengan H4 relative to EMA50
    - LONG: Price > EMA50
    - SHORT: Price < EMA50
    """
    if df is None or df.empty:
        return {"aligned": False, "reason": "No Data"}
    
    last = df.iloc[-1]
    close = last["close"]
    ema50 = last["EMA50"]
    
    aligned = False
    if h4_direction == "LONG" and close > ema50:
        aligned = True
    elif h4_direction == "SHORT" and close < ema50:
        aligned = True
        
    return {
        "aligned": aligned,
        "reason": "H1 Price vs EMA50 Agreement" if aligned else "H1 Divergence (Choppy/Pullback)"
    }

# ================================================================
#  CONTEXT BUILDER (CORE)
# ================================================================
def build_ai_context(symbol: str, user_chart_context: str | None = None):
    # 1. Fetch ALL Timeframes
    df_h4 = fetch_market_data(symbol, "4h", limit=300)
    df_h1 = fetch_market_data(symbol, "1h", limit=100)
    df_m30 = fetch_market_data(symbol, "30m", limit=100)
    df_m15 = fetch_market_data(symbol, "15m", limit=100)

    # 2. Apply Indicators
    df_h4 = apply_indicators(df_h4, "4h")
    df_h1 = apply_indicators(df_h1, "1h")
    df_m30 = apply_indicators(df_m30, "30m")
    df_m15 = apply_indicators(df_m15, "15m")

    # Critical Data Check
    if df_h4 is None or df_m15 is None:
        return None

    # 3. Analyze Higher Timeframes
    trend_h4 = detect_trend_h4(df_h4)
    bias_h1 = detect_bias_h1(df_h1, trend_h4["direction"])

    # 4. Package Context
    last_m15 = df_m15.iloc[-1]
    
    context = {
        "symbol": symbol,
        "price": float(last_m15["close"]),
        "volume": float(last_m15["volume"]),
        "atr": float(last_m15.get("ATR", 0)),
        
        # Analysis
        "trend_h4": trend_h4,
        "bias_h1": bias_h1,
        
        # Raw Data (for M30/M15 modules)
        "df_m30": df_m30,
        "df_m15": df_m15,
        
        "user_context": user_chart_context or ""
    }
    return context

# ================================================================
#  TECHNICAL EVALUATOR (ANCHOR & BIAS CHECKER)
# ================================================================
def evaluate_technical(data):
    """
    Validates Step 1 (H4) & Step 2 (H1).
    Full Execution logic (M30/M15) happens in ai_engine.py
    """
    trend = data.get("trend_h4", {})
    bias = data.get("bias_h1", {})

    # 1. H4 Must be Valid
    if not trend.get("valid"):
        return {
            "valid": False, 
            "reason": f"H4 Trend Invalid or ADX Low ({trend.get('adx',0):.1f})"
        }

    direction = trend["direction"]

    # 2. H1 Should Confirm (Soft Filter)
    # Jika H1 divergence, confidence turun drastis, tapi tidak selalu NO_TRADE (bisa pullback entry)
    # Tapi sesuai request Anda: "Trade hanya dieksekusi jika semua terpenuhi" -> H1 Bias Searah
    if not bias.get("aligned"):
         return {
            "valid": False, 
            "reason": "H1 Bias Divergence (Price vs EMA50 mismatch with H4)"
        }

    return {
        "valid": True,
        "direction": direction,
        "confidence": 0.80 
    }