import pandas as pd
import pandas_ta as ta

# ================================================================
# BASIC INDICATOR LOGIC
# ================================================================
def compute_atr(df, length=14):
    atr_series = ta.atr(df["high"], df["low"], df["close"], length)
    return float(atr_series.iloc[-1])

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

    # 1. Global Indicator: Volume Moving Average (untuk validasi entry/breakout)
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
        # Supply Demand zones biasanya butuh library external/logic kompleks,
        # di sini kita pakai price action vs EMA50 sebagai proxy bias.

    # 4. M30 (Setup): VWAP, EMA20, EMA50
    elif tf == "30m":
        # VWAP biasanya butuh data volume & high/low/close yang presisi
        try:
            df["VWAP"] = ta.vwap(df["high"], df["low"], df["close"], df["volume"])
        except:
            # Fallback jika VWAP error (misal data kurang)
            df["VWAP"] = ta.ema(df["close"], 20) 
        
        df["EMA20"] = ta.ema(df["close"], 20)
        df["EMA50"] = ta.ema(df["close"], 50)

    # 5. M15 (Execution): EMA20, ATR
    elif tf == "15m":
        df["EMA20"] = ta.ema(df["close"], 20)
        df["ATR"] = ta.atr(df["high"], df["low"], df["close"], 14)

    df.dropna(inplace=True)
    return df

# ================================================================
# MARKET STRUCTURE (Simplified)
# ================================================================
def compute_trend_structure(df):
    closes = df["close"].tail(20).values
    if closes[-1] > closes[-5] > closes[-10]:
        return "LONG"
    elif closes[-1] < closes[-5] < closes[-10]:
        return "SHORT"
    return "NEUTRAL"