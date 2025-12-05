import ccxt
import pandas as pd
import pandas_ta as ta
import numpy as np

from backend.indicators import (
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
        ohlcv = exc.fetch_ohlcv(symbol, timeframe, limit=limit)
    except Exception as e:
        print("FETCH ERROR:", e)
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
    """
    Wrapper agar semua indikator terpusat di indicators.py.
    """
    if df is None or df.empty:
        return None
    return apply_indicators_by_tf(df, tf)


# ================================================================
#  TREND DETECTION (Institutional Bias)
# ================================================================
def detect_trend(df):
    """
    Institutional trend bias:
    LONG  = EMA50 > EMA200
    SHORT = EMA50 < EMA200
    """
    if df is None or len(df) < 200:
        return {"valid": False}

    last = df.iloc[-1]

    if last["EMA50"] > last["EMA200"]:
        return {"valid": True, "direction": "LONG"}
    elif last["EMA50"] < last["EMA200"]:
        return {"valid": True, "direction": "SHORT"}
    return {"valid": False}


# ================================================================
#  CONTEXT BUILDER (CORE)
# ================================================================
def build_ai_context(symbol: str, user_chart_context: str | None = None):

    # 15m = main operational timeframe
    df = fetch_market_data(symbol, "15m")
    if df is None or len(df) < 100:
        return None

    df = apply_indicators(df, "15m")
    if df is None or df.empty:
        return None

    # Higher TF for trend
    trend_df = fetch_market_data(symbol, "4h", limit=300)
    trend_df = apply_indicators(trend_df, "4h")

    trend = detect_trend(trend_df)
    market_structure = compute_trend_structure(df)

    last = df.iloc[-1]

    context = {
        "symbol": symbol,
        "price": float(last["close"]),
        "volume": float(last["volume"]),
        "atr": float(last.get("ATR", compute_atr(df))),
        "trend": trend,
        "market_structure": market_structure,
        "user_context": user_chart_context or ""
    }
    return context


# ================================================================
#  TECHNICAL EVALUATOR (Used by AI pipeline)
# ================================================================
def evaluate_technical(data):
    trend = data.get("trend")

    if not trend or not trend.get("valid"):
        return {"valid": False, "reason": "Trend invalid"}

    direction = trend["direction"]

    # Confidence calculation ringan (rule-based)
    base_conf = 0.70
    if data.get("market_structure") == direction:
        base_conf += 0.12

    return {
        "valid": True,
        "direction": direction,
        "confidence": round(base_conf, 3)
    }
