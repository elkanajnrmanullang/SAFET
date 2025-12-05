import pandas as pd
import pandas_ta as ta


# ================================================================
# BASIC INDICATOR LOGIC
# ================================================================
def compute_atr(df, length=14):
    atr_series = ta.atr(df["high"], df["low"], df["close"], length)
    return float(atr_series.iloc[-1])


def compute_emas(df):
    df["EMA20"] = ta.ema(df["close"], 20)
    df["EMA50"] = ta.ema(df["close"], 50)
    df["EMA200"] = ta.ema(df["close"], 200)
    return df


def compute_vwap(df):
    df["VWAP"] = ta.vwap(df["high"], df["low"], df["close"], df["volume"])
    return df


def compute_adx(df):
    adx = ta.adx(df["high"], df["low"], df["close"], 14)
    df["ADX"] = adx["ADX_14"]
    return df


# ================================================================
# HIGH-LEVEL TF-BASED INDICATORS
# ================================================================
def apply_indicators_by_tf(df, tf):
    df = df.copy()

    # Shared
    df["Vol_MA20"] = df["volume"].rolling(20).mean()

    if tf in ["4h", "1h"]:
        df = compute_emas(df)
        df = compute_adx(df)

    elif tf == "30m":
        df = compute_emas(df)
        df = compute_vwap(df)

    elif tf == "15m":
        df = compute_emas(df)
        df["ATR"] = ta.atr(df["high"], df["low"], df["close"], 14)

    df.dropna(inplace=True)
    return df


# ================================================================
# MARKET STRUCTURE (Simplified)
# ================================================================
def compute_trend_structure(df):
    """
    Simpel market structure:
    Jika higher lows → LONG
    Jika lower highs → SHORT
    Jika noise → NEUTRAL
    """
    closes = df["close"].tail(20).values

    if closes[-1] > closes[-5] > closes[-10]:
        return "LONG"
    elif closes[-1] < closes[-5] < closes[-10]:
        return "SHORT"
    return "NEUTRAL"
