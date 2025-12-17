import ccxt
import pandas as pd
import pandas_ta as ta
import numpy as np
import math

# Config Import
from backend.core.config import config

# Analytics Import
from backend.analytics.indicators import (
    apply_indicators_by_tf,
    compute_atr,
    compute_atr_sma,
    compute_trend_structure,
    detect_rsi_divergence
)

# EXCHANGE CONNECTION
def get_exchange():
    return ccxt.binance({
        "enableRateLimit": True,
        "options": {"defaultType": "future"},
        "timeout": 10000,
    })

# MARKET DATA FETCH
def fetch_market_data(symbol, timeframe, limit=None):
    if limit is None:
        limit = config.MAX_CANDLE_LIMIT

    exc = get_exchange()
    try:
        safe_symbol = (
            symbol.replace("USDT", "/USDT").upper()
            if "/" not in symbol else symbol.upper()
        )
        
        ohlcv = exc.fetch_ohlcv(safe_symbol, timeframe, limit=limit)
    
    except ccxt.NetworkError as e:
        print(f"NETWORK ERROR ({symbol}): {str(e)}")
        return None
    except Exception as e:
        print(f"FETCH ERROR ({symbol} - {timeframe}): {str(e)}")
        return None

    if not ohlcv:
        return None

    df = pd.DataFrame(
        ohlcv,
        columns=["timestamp", "open", "high", "low", "close", "volume"]
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df

# SYMBOL FETCHER
def get_top_symbols(limit=50):
    exc = get_exchange()
    try:
        exc.load_markets()
        tickers = exc.fetch_tickers()
        
        valid_tickers = []
        for symbol, data in tickers.items():
            if "/USDT" in symbol and "quoteVolume" in data:
                bad_tokens = ["USDC/", "BUSD/", "DAI/", "TUSD/", "FDUSD/", "USDP/", "EUR/", "UP/", "DOWN/", "BEAR/", "BULL/"]
                if not any(exclude in symbol for exclude in bad_tokens):
                     valid_tickers.append((symbol, data["quoteVolume"]))
        
        valid_tickers.sort(key=lambda x: x[1], reverse=True)
        top_list = [t[0] for t in valid_tickers[:limit]]
        
        if not top_list:
            raise Exception("No tickers found.")
            
        return top_list

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        return []

# INDICATOR WRAPPER
def apply_indicators(df, tf):
    if df is None or df.empty:
        return None
    return apply_indicators_by_tf(df, tf)

# PATTERN SENTIMENT HELPER
def _get_pattern_sentiment(pattern_name: str) -> str:
    if not pattern_name:
        return "NEUTRAL"
    
    p = pattern_name.lower()
    
    bullish_keywords = [
        "bull", "ascending", "cup", "double bottom", "inverse head", 
        "falling wedge", "flag", "pennant", "morning"
    ]
    bearish_keywords = [
        "bear", "descending", "double top", "head and shoulders", 
        "rising wedge", "evening", "shooting"
    ]
    
    if "bull" in p: return "LONG"
    if "bear" in p: return "SHORT"

    if any(k in p for k in bullish_keywords): return "LONG"
    if any(k in p for k in bearish_keywords): return "SHORT"
    
    return "NEUTRAL"

# H4 TREND DETECTION
def detect_trend_h4(df, adx_value):
    if df is None or len(df) < 200:
        return {"valid": False, "direction": "NEUTRAL", "adx": 0, "exhaustion": False, "reason": "Data Insufficient"}

    last = df.iloc[-1]
    adx_val = float(adx_value)
    
    # ADX Filter
    if adx_val < config.ADX_NORMAL_THRESHOLD:
        return {
            "valid": False, 
            "direction": "NEUTRAL", 
            "adx": adx_val, 
            "exhaustion": False, 
            "reason": f"Market Choppy/Sideways (ADX < {config.ADX_NORMAL_THRESHOLD:.1f})"
        }
    
    # Adaptive Structure
    structure_label, window_size = compute_trend_structure(df, adx_val)
    
    if structure_label == "NEUTRAL":
         return {
            "valid": False, 
            "direction": "NEUTRAL", 
            "adx": adx_val, 
            "exhaustion": False, 
            "reason": f"H4 Structure Invalid (NEUTRAL in W{window_size})"
        }

    # EMA Alignment
    ema_direction = "NEUTRAL"
    if last["EMA50"] > last["EMA200"]:
        ema_direction = "LONG"
    elif last["EMA50"] < last["EMA200"]:
        ema_direction = "SHORT"
        
    # Final Alignment Check
    final_direction = "NEUTRAL"
    valid = False
    
    if ema_direction == structure_label and ema_direction != "NEUTRAL":
        final_direction = ema_direction
        valid = True
    
    # Exhaustion Warning
    is_exhausted, exhaust_reason = detect_rsi_divergence(df, final_direction)
    
    if valid:
        reason_msg = f"H4 EMA({ema_direction}) + Struct({structure_label} W{window_size}) Match, ADX={adx_val:.1f}"
        if is_exhausted:
            reason_msg += f" | ⚠️ EXHAUSTION: {exhaust_reason}"
    else:
        reason_msg = f"H4 Alignment Failed: EMA({ema_direction}) vs Struct({structure_label} W{window_size})"
        
    return {
        "valid": valid, 
        "direction": final_direction, 
        "adx": float(adx_val),
        "exhaustion": is_exhausted,
        "reason": reason_msg
    }

# H1 BIAS DETECTION
def detect_bias_h1(df, h4_direction):
    if df is None or df.empty or len(df) < 20 or "ATR" not in df.columns or "EMA50" not in df.columns:
        return {"aligned": False, "reason": "No Data", "volatility": "NO_DATA"}

    last = df.iloc[-1]
    close = last["close"]
    ema50 = last["EMA50"]
    atr_now = last.get("ATR", 0)
    
    # Price Alignment
    aligned = False
    if h4_direction == "LONG" and close > ema50:
        aligned = True
    elif h4_direction == "SHORT" and close < ema50:
        aligned = True
    
    if not aligned:
        return {
            "aligned": False,
            "reason": "H1 Price Divergence (Close vs EMA50)",
            "volatility": "NO_TRADE"
        }

    # Volatility Gate
    volatility_status = "NORMAL"
    reason_msg = "H1 Price vs EMA50 Agreement"
    
    if atr_now == 0 or len(df) < 20:
        volatility_status = "NO_DATA"
    else:
        atr_sma = compute_atr_sma(df, length=20)
        
        if atr_sma == 0:
            volatility_status = "NO_DATA"
        elif atr_now > atr_sma * config.ATR_OVERHEAT_MULTIPLIER:
            volatility_status = "OVERHEAT"
            reason_msg += " | Volatility OVERHEAT (>1.5x Avg ATR)"
        elif atr_now < atr_sma * config.ATR_LESU_MULTIPLIER:
            volatility_status = "LESU"
            reason_msg += " | Volatility LESU (<1.0x Avg ATR)"
        else:
            volatility_status = "NORMAL"
            reason_msg += f" | Volatility NORMAL ({atr_now/atr_sma:.2f}x Avg ATR)"

    return {
        "aligned": aligned,
        "reason": reason_msg,
        "volatility": volatility_status
    }

# CONTEXT BUILDER
def build_ai_context(symbol: str, user_chart_context: str | None = None):
    limit = config.MAX_CANDLE_LIMIT
    
    # Data Fetching
    df_h4 = fetch_market_data(symbol, "4h", limit=limit)
    df_h1 = fetch_market_data(symbol, "1h", limit=limit)
    df_m30 = fetch_market_data(symbol, "30m", limit=limit)
    df_m15 = fetch_market_data(symbol, "15m", limit=limit)

    # Indicator Application
    df_h4 = apply_indicators(df_h4, "4h")
    df_h1 = apply_indicators(df_h1, "1h")
    df_m30 = apply_indicators(df_m30, "30m")
    df_m15 = apply_indicators(df_m15, "15m")

    if df_h4 is None or df_m15 is None:
        return None

    # H4 ADX Analysis
    h4_adx = df_h4.iloc[-1].get("ADX", 0) if df_h4 is not None and "ADX" in df_h4.columns else 0

    # Trend H4 Analysis
    trend_h4 = detect_trend_h4(df_h4, h4_adx)
    
    # Bias H1 Analysis
    bias_h1 = detect_bias_h1(df_h1, trend_h4["direction"])

    last_m15 = df_m15.iloc[-1]
    
    context = {
        "symbol": symbol,
        "price": float(last_m15["close"]),
        "volume": float(last_m15["volume"]),
        "atr": float(last_m15.get("ATR", 0)),
        "trend_h4": trend_h4,
        "bias_h1": bias_h1,
        "df_m30": df_m30,
        "df_m15": df_m15,
        "user_context": user_chart_context or ""
    }
    return context

# TECHNICAL EVALUATOR
def evaluate_technical(data):
    trend = data.get("trend_h4", {})
    bias = data.get("bias_h1", {})

    # Trend Validation
    if not trend.get("valid"):
        return {
            "valid": False, 
            "reason": f"H4 Trend Invalid: {trend.get('reason', 'Unknown')}"
        }

    direction = trend["direction"]
    volatility = bias.get("volatility")

    # Volatility Check
    if volatility == "LESU":
         return {
            "valid": False, 
            "reason": "H1 Volatility Gate: Market Lesu (Delay Trade)"
        }
        
    # Bias Validation
    if not bias.get("aligned"):
         return {
            "valid": False, 
            "reason": "H1 Bias Divergence (Price vs EMA50 mismatch with H4)"
        }

    # User Pattern Validation
    user_pattern = data.get("user_context", "")
    if user_pattern:
        pat_sentiment = _get_pattern_sentiment(user_pattern)
        if pat_sentiment != "NEUTRAL" and pat_sentiment != direction:
             return {
                "valid": False, 
                "reason": f"H1 Context Conflict: User Pattern '{user_pattern}' ({pat_sentiment}) berlawanan dengan H1 Bias ({direction})"
            }

    return {
        "valid": True,
        "direction": direction,
        "confidence": 0.80,
        "volatility": volatility
    }