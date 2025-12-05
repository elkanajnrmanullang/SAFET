"""
Mini CHOCH / BOS Detector
-------------------------
Dipakai sebagai validasi micro-structure (15m) sebelum trade diizinkan.

Rules:
- BOS = price menembus swing high/low sebelumnya
- CHOCH = dari bearish ke bullish atau sebaliknya (dilihat dari struktur 3 swing)
"""

from backend.crypto_data import fetch_market_data


def _find_swings(df):
    """
    Identify swing high / swing low sederhana.
    Tidak ultra kompleks agar pipeline tetap stabil.
    """
    highs = []
    lows = []

    for i in range(2, len(df) - 2):
        # swing high
        if df["high"][i] > df["high"][i-1] and df["high"][i] > df["high"][i+1]:
            highs.append((df["timestamp"][i], df["high"][i]))

        # swing low
        if df["low"][i] < df["low"][i-1] and df["low"][i] < df["low"][i+1]:
            lows.append((df["timestamp"][i], df["low"][i]))

    return highs[-3:], lows[-3:]   # only last 3 swings


def detect_microstructure(symbol: str):
    df = fetch_market_data(symbol, "15m")
    if df is None or len(df) < 50:
        return {
            "signal": "NONE",
            "reason": "insufficient data"
        }

    highs, lows = _find_swings(df)
    if not highs or not lows:
        return {"signal": "NONE", "reason": "no swings"}

    last_price = df["close"].iloc[-1]

    last_high = highs[-1][1]
    prev_high = highs[-2][1] if len(highs) >= 2 else None

    last_low = lows[-1][1]
    prev_low = lows[-2][1] if len(lows) >= 2 else None

    # -------------------------------
    # BOS Detection
    # -------------------------------
    if prev_high and last_price > prev_high:
        return {
            "signal": "BOS_UP",
            "last_swing_high": last_high,
            "last_swing_low": last_low
        }

    if prev_low and last_price < prev_low:
        return {
            "signal": "BOS_DOWN",
            "last_swing_high": last_high,
            "last_swing_low": last_low
        }

    # -------------------------------
    # CHOCH Detection (trend flip)
    # -------------------------------
    # bullish choch = break previous low then break previous high
    if prev_low and prev_high:
        if last_price < prev_low and last_price > prev_high:
            return {
                "signal": "CHOCH_UP",
                "last_swing_high": last_high,
                "last_swing_low": last_low
            }

        if last_price > prev_high and last_price < prev_low:
            return {
                "signal": "CHOCH_DOWN",
                "last_swing_high": last_high,
                "last_swing_low": last_low
            }

    # default
    return {
        "signal": "NONE",
        "last_swing_high": last_high,
        "last_swing_low": last_low
    }
