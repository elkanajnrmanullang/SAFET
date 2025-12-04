import ccxt
import pandas as pd
import pandas_ta as ta
import numpy as np

# =============================
# CONNECTION
# =============================
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
        columns=["timestamp","open","high","low","close","volume"]
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df


# =============================
# INDICATORS BY TF
# =============================
def apply_indicators(df, tf):
    if df is None or df.empty:
        return None

    # shared
    df["Vol_MA20"] = df["volume"].rolling(20).mean()

    if tf in ["4h", "1h"]:
        df["EMA50"] = ta.ema(df["close"], 50)
        df["EMA200"] = ta.ema(df["close"], 200)
        df["ADX"] = ta.adx(
            df["high"], df["low"], df["close"], 14
        )["ADX_14"]

    if tf == "30m":
        df["EMA20"] = ta.ema(df["close"], 20)
        df["EMA50"] = ta.ema(df["close"], 50)
        df["VWAP"] = ta.vwap(
            df["high"], df["low"], df["close"], df["volume"]
        )

    if tf == "15m":
        df["EMA20"] = ta.ema(df["close"], 20)
        df["ATR"] = ta.atr(
            df["high"], df["low"], df["close"], 14
        )

    df.dropna(inplace=True)
    return df


# =============================
# TREND DETECTION (MINIMAL & STABLE)
# =============================
def detect_trend(df):
    """
    Simple institutional bias:
    EMA50 vs EMA200
    """
    if df is None or len(df) < 200:
        return {"valid": False}

    last = df.iloc[-1]

    if last["EMA50"] > last["EMA200"]:
        return {"valid": True, "direction": "LONG"}
    elif last["EMA50"] < last["EMA200"]:
        return {"valid": True, "direction": "SHORT"}
    else:
        return {"valid": False}


# =============================
# CONTEXT BUILDER (CORE)
# =============================
def build_ai_context(symbol: str, user_chart_context: str | None = None):

    # ❌ SALAH (DIHAPUS)
    # df = fetch_ohlcv(symbol)

    # ✅ BENAR
    df = fetch_market_data(symbol, "15m")

    if df is None or df.empty or len(df) < 100:
        return None

    df = apply_indicators(df, "15m")
    if df is None or df.empty:
        return None

    trend_df = fetch_market_data(symbol, "4h", limit=300)
    trend_df = apply_indicators(trend_df, "4h")

    trend = detect_trend(trend_df)

    last = df.iloc[-1]

    context = {
        "symbol": symbol,
        "price": float(last["close"]),
        "volume": float(last["volume"]),
        "atr": float(last["ATR"]),
        "trend": trend,
        "user_context": user_chart_context or ""
    }

    return context


# =============================
# TECHNICAL EVALUATOR
# =============================
def evaluate_technical(data):
    """
    Dipakai oleh ai_engine.run_ai_pipeline
    """

    trend = data.get("trend")

    if not trend or not trend.get("valid"):
        return {"valid": False, "reason": "Trend invalid"}

    return {
        "valid": True,
        "direction": trend["direction"],
        "confidence": 0.82
    }
