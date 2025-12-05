"""
Forex Data Loader
-----------------
Mirror dari crypto_data.py tetapi menggunakan yfinance.

Tujuan:
- Menjaga kompatibilitas pipeline
- Bisa dipakai saat user beralih ke FX

Function utama:
- fetch_fx_data()
- apply_indicators_fx()
- build_fx_context()
"""

import pandas as pd
import pandas_ta as ta
import yfinance as yf


# =============================
# FETCH DATA
# =============================
def fetch_fx_data(symbol: str, timeframe: str = "15m", limit: int = 500):
    """
    symbol contoh: "EURUSD=X"
    timeframe mapping:
        15m -> 15m
        1h -> 1h
        4h -> 4h
    """
    try:
        df = yf.download(
            tickers=symbol,
            interval=timeframe,
            period="90d"
        )
        if df is None or df.empty:
            return None

        df = df.rename(columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume"
        })
        df.reset_index(inplace=True)
        df = df.tail(limit)
        return df

    except Exception:
        return None


# =============================
# APPLY INDICATORS
# =============================
def apply_indicators_fx(df, tf):
    if df is None or df.empty:
        return None

    df["Vol_MA20"] = df["volume"].rolling(20).mean()

    if tf in ["4h", "1h"]:
        df["EMA50"] = ta.ema(df["close"], 50)
        df["EMA200"] = ta.ema(df["close"], 200)
        df["ADX"] = ta.adx(df["high"], df["low"], df["close"], 14)["ADX_14"]

    if tf == "15m":
        df["EMA20"] = ta.ema(df["close"], 20)
        df["ATR"] = ta.atr(df["high"], df["low"], df["close"], 14)

    df.dropna(inplace=True)
    return df


# =============================
# CONTEXT BUILDER
# =============================
def build_fx_context(symbol: str):
    df = fetch_fx_data(symbol)

    if df is None or df.empty:
        return None

    df = apply_indicators_fx(df, "15m")
    if df is None or df.empty:
        return None

    last = df.iloc[-1]

    ctx = {
        "symbol": symbol,
        "price": float(last["close"]),
        "volume": float(last["volume"]),
        "atr": float(last["ATR"]),
        "trend": "FX minimal trend (EMA20 placeholder)",
    }

    return ctx
