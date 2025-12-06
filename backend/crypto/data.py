import ccxt
import pandas as pd
import pandas_ta as ta
import numpy as np

# Import dari analytics
from backend.analytics.indicators import (
    apply_indicators_by_tf,
    compute_atr,
    compute_trend_structure
)

# ================================================================
#  CONNECTION
# ================================================================
def get_exchange():
    """
    Inisialisasi koneksi CCXT.
    PENTING: Pastikan VPN aktif atau gunakan Proxy jika di Indonesia.
    """
    return ccxt.binance({
        "enableRateLimit": True,
        "options": {"defaultType": "future"},
        # Tambahkan timeout agar tidak hang terlalu lama jika diblokir
        "timeout": 10000,  # 10 detik
    })

def fetch_market_data(symbol, timeframe, limit=500):
    exc = get_exchange()
    try:
        # Safety: Pastikan format symbol benar
        safe_symbol = (
            symbol.replace("USDT", "/USDT").upper()
            if "/" not in symbol else symbol.upper()
        )
        
        # Coba ambil data
        ohlcv = exc.fetch_ohlcv(safe_symbol, timeframe, limit=limit)
    
    except ccxt.NetworkError as e:
        print(f"NETWORK ERROR ({symbol}): Koneksi ke Binance gagal. Cek VPN! ({str(e)})")
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

# ================================================================
#  DYNAMIC SYMBOL FETCHER (PURE REAL-TIME)
# ================================================================
def get_top_symbols(limit=50):
    """
    Mengambil Top N Koin berdasarkan Volume 24 Jam dari Binance Futures.
    """
    exc = get_exchange()
    try:
        # Load markets membutuhkan koneksi stabil
        exc.load_markets()
        tickers = exc.fetch_tickers()
        
        valid_tickers = []
        for symbol, data in tickers.items():
            if "/USDT" in symbol and "quoteVolume" in data:
                # Filter stablecoin pairs & leverage tokens
                bad_tokens = ["USDC/", "BUSD/", "DAI/", "TUSD/", "FDUSD/", "USDP/", "EUR/", "UP/", "DOWN/", "BEAR/", "BULL/"]
                if not any(exclude in symbol for exclude in bad_tokens):
                     valid_tickers.append((symbol, data["quoteVolume"]))
        
        valid_tickers.sort(key=lambda x: x[1], reverse=True)
        top_list = [t[0] for t in valid_tickers[:limit]]
        
        if not top_list:
            raise Exception("Exchange connect success but 0 tickers found.")
            
        return top_list

    except ccxt.NetworkError:
        print("CRITICAL: Network Error saat mengambil Top Symbols. Pastikan VPN ON.")
        return []
    except Exception as e:
        print(f"CRITICAL: Gagal mengambil Top Symbols dari Binance. Error: {e}")
        return []

# ... (Sisa fungsi indikator dan evaluate_technical biarkan sama) ...
# ================================================================
#  INDICATOR WRAPPER
# ================================================================
def apply_indicators(df, tf):
    if df is None or df.empty:
        return None
    return apply_indicators_by_tf(df, tf)

def detect_trend_h4(df):
    if df is None or len(df) < 200:
        return {"valid": False, "direction": "NEUTRAL", "adx": 0}

    last = df.iloc[-1]
    adx_val = float(last.get("ADX", 0) or 0)
    
    direction = "NEUTRAL"
    if last["EMA50"] > last["EMA200"]:
        direction = "LONG"
    elif last["EMA50"] < last["EMA200"]:
        direction = "SHORT"
        
    valid = False
    if direction != "NEUTRAL" and adx_val >= 20:
        valid = True
    
    return {
        "valid": valid, 
        "direction": direction, 
        "adx": float(adx_val),
        "reason": f"H4 EMA Alignment ({direction}), ADX={adx_val:.2f}"
    }

def detect_bias_h1(df, h4_direction):
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
        "reason": "H1 Price vs EMA50 Agreement" if aligned else "H1 Divergence"
    }

def build_ai_context(symbol: str, user_chart_context: str | None = None):
    # Fetch Data
    df_h4 = fetch_market_data(symbol, "4h", limit=500)
    df_h1 = fetch_market_data(symbol, "1h", limit=500)
    df_m30 = fetch_market_data(symbol, "30m", limit=500)
    df_m15 = fetch_market_data(symbol, "15m", limit=500)

    # Apply Indicators
    df_h4 = apply_indicators(df_h4, "4h")
    df_h1 = apply_indicators(df_h1, "1h")
    df_m30 = apply_indicators(df_m30, "30m")
    df_m15 = apply_indicators(df_m15, "15m")

    if df_h4 is None or df_m15 is None:
        return None

    # Analyze
    trend_h4 = detect_trend_h4(df_h4)
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

def evaluate_technical(data):
    trend = data.get("trend_h4", {})
    bias = data.get("bias_h1", {})

    if not trend.get("valid"):
        return {
            "valid": False, 
            "reason": f"H4 Trend Invalid or ADX Low ({trend.get('adx',0):.1f})"
        }

    direction = trend["direction"]

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