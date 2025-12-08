import ccxt
import pandas as pd
import pandas_ta as ta
import numpy as np
import math # <-- BARU: Diperlukan untuk operasi matematika

# Import Config untuk Limit Candle (1000)
from backend.core.config import config

# Import dari analytics
from backend.analytics.indicators import (
    apply_indicators_by_tf,
    compute_atr,
    compute_atr_sma, # <-- BARU: Untuk Volatility Gate
    compute_trend_structure,
    detect_rsi_divergence # <-- BARU: Untuk Exhaustion Warning
)

# ================================================================
#  CONNECTION & MARKET DATA FETCH (TIDAK BERUBAH)
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

def fetch_market_data(symbol, timeframe, limit=None):
    # Jika limit tidak ditentukan, ambil dari config global (default 1000)
    if limit is None:
        limit = config.MAX_CANDLE_LIMIT

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
#  DYNAMIC SYMBOL FETCHER & INDICATOR WRAPPER (TIDAK BERUBAH)
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

# ================================================================
#  INDICATOR WRAPPER (TIDAK BERUBAH)
# ================================================================
def apply_indicators(df, tf):
    if df is None or df.empty:
        return None
    return apply_indicators_by_tf(df, tf)

# TAMBAHKAN HELPER INI UNTUK MEMBACA SENTIMEN POLA USER (TIDAK BERUBAH)
def _get_pattern_sentiment(pattern_name: str) -> str:
    """
    Mapping sederhana untuk validasi arah pola chart manual user.
    """
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
    
    # Cek keyword 'bull' atau 'bear' eksplisit dulu
    if "bull" in p: return "LONG"
    if "bear" in p: return "SHORT"

    # Cek keyword spesifik
    if any(k in p for k in bullish_keywords): return "LONG"
    if any(k in p for k in bearish_keywords): return "SHORT"
    
    return "NEUTRAL"

# [UPDATE] DETECT TREND H4 (Anchor)
def detect_trend_h4(df, adx_value):
    """
    Mendeteksi Trend H4 (Anchor).
    Valid = EMA Alignment + Adaptive Structure Alignment + ADX >= 20
    + Menambahkan Exhaustion Warning (RSI Divergence)
    """
    if df is None or len(df) < 200:
        return {"valid": False, "direction": "NEUTRAL", "adx": 0, "exhaustion": False, "reason": "Data Insufficient"}

    last = df.iloc[-1]
    adx_val = float(adx_value)
    
    # 1. Hard Filter: ADX < 20 (NO_TRADE)
    if adx_val < config.ADX_NORMAL_THRESHOLD:
        return {
            "valid": False, 
            "direction": "NEUTRAL", 
            "adx": adx_val, 
            "exhaustion": False, 
            "reason": f"Market Choppy/Sideways (ADX < {config.ADX_NORMAL_THRESHOLD:.1f})"
        }
    
    # 2. Adaptive Structure
    # Hitung Structure dengan Adaptive Window berdasarkan ADX
    structure_label, window_size = compute_trend_structure(df, adx_val)
    
    # Safety check: Jika structure gagal terdeteksi di window adaptif
    if structure_label == "NEUTRAL":
         return {
            "valid": False, 
            "direction": "NEUTRAL", 
            "adx": adx_val, 
            "exhaustion": False, 
            "reason": f"H4 Structure Invalid (NEUTRAL in W{window_size})"
        }

    # 3. EMA Alignment
    ema_direction = "NEUTRAL"
    if last["EMA50"] > last["EMA200"]:
        ema_direction = "LONG"
    elif last["EMA50"] < last["EMA200"]:
        ema_direction = "SHORT"
        
    # 4. Final Alignment Check (Struktur vs EMA)
    final_direction = "NEUTRAL"
    valid = False
    
    # Rule: EMA & Structure harus searah
    if ema_direction == structure_label and ema_direction != "NEUTRAL":
        final_direction = ema_direction
        valid = True
    
    # 5. Exhaustion Warning (RSI Divergence)
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

# [UPDATE] DETECT BIAS H1 (Confirmation - Bias)
def detect_bias_h1(df, h4_direction):
    """
    Mendeteksi Bias H1: Price Alignment (Close vs EMA50) + Volatility Gate (ATR vs SMA(ATR)).
    """
    if df is None or df.empty or len(df) < 20 or "ATR" not in df.columns or "EMA50" not in df.columns:
        return {"aligned": False, "reason": "No Data", "volatility": "NO_DATA"}

    last = df.iloc[-1]
    close = last["close"]
    ema50 = last["EMA50"]
    atr_now = last.get("ATR", 0)
    
    # --- 1. Price Alignment (WAJIB) ---
    aligned = False
    if h4_direction == "LONG" and close > ema50:
        aligned = True
    elif h4_direction == "SHORT" and close < ema50:
        aligned = True
    
    # Jika tidak aligned, langsung FAIL (H4-H1 Divergence)
    if not aligned:
        return {
            "aligned": False,
            "reason": "H1 Price Divergence (Close vs EMA50)",
            "volatility": "NO_TRADE"
        }

    # --- 2. Volatility Gate ---
    volatility_status = "NORMAL"
    reason_msg = "H1 Price vs EMA50 Agreement"
    
    if atr_now == 0 or len(df) < 20:
        volatility_status = "NO_DATA"
    else:
        # Panggil ATR SMA
        atr_sma = compute_atr_sma(df, length=20)
        
        if atr_sma == 0:
            volatility_status = "NO_DATA"
        elif atr_now > atr_sma * config.ATR_OVERHEAT_MULTIPLIER:
            volatility_status = "OVERHEAT"
            reason_msg += " | Volatility OVERHEAT (>1.5x Avg ATR)"
        elif atr_now < atr_sma * config.ATR_LESU_MULTIPLIER: # LESU jika < 1.0x Avg ATR
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

# [UPDATE] BUILD AI CONTEXT (H4/H1 Orchestration)
def build_ai_context(symbol: str, user_chart_context: str | None = None):
    # Gunakan Limit Global dari Config (1000 Candle)
    limit = config.MAX_CANDLE_LIMIT
    
    # Fetch Data
    df_h4 = fetch_market_data(symbol, "4h", limit=limit)
    df_h1 = fetch_market_data(symbol, "1h", limit=limit)
    df_m30 = fetch_market_data(symbol, "30m", limit=limit) # M30 butuh history cukup untuk swing
    df_m15 = fetch_market_data(symbol, "15m", limit=limit)

    # Apply Indicators
    df_h4 = apply_indicators(df_h4, "4h")
    df_h1 = apply_indicators(df_h1, "1h")
    df_m30 = apply_indicators(df_m30, "30m")
    df_m15 = apply_indicators(df_m15, "15m")

    if df_h4 is None or df_m15 is None:
        return None

    # [NEW] Analyze H4 ADX
    h4_adx = df_h4.iloc[-1].get("ADX", 0) if df_h4 is not None and "ADX" in df_h4.columns else 0

    # Analyze Trend H4 (Anchor)
    trend_h4 = detect_trend_h4(df_h4, h4_adx)
    
    # Analyze Bias H1
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

# [UPDATE] EVALUATE TECHNICAL (Gatekeeper Final)
def evaluate_technical(data):
    trend = data.get("trend_h4", {})
    bias = data.get("bias_h1", {})

    # 1. Cek Validitas Trend Utama (H4)
    if not trend.get("valid"):
        return {
            "valid": False, 
            "reason": f"H4 Trend Invalid: {trend.get('reason', 'Unknown')}"
        }

    direction = trend["direction"]
    volatility = bias.get("volatility")

    # 2. Cek Volatility (DELAY jika Lesu)
    if volatility == "LESU":
         return {
            "valid": False, 
            "reason": "H1 Volatility Gate: Market Lesu (Delay Trade)"
        }
        
    # 3. Cek Validitas Bias (H1) - Price Alignment
    if not bias.get("aligned"):
         return {
            "valid": False, 
            "reason": "H1 Bias Divergence (Price vs EMA50 mismatch with H4)"
        }

    # 4. Validasi Context Pattern User (Pindah ke H1 Check)
    user_pattern = data.get("user_context", "")
    if user_pattern:
        pat_sentiment = _get_pattern_sentiment(user_pattern)
        # Check against direction (H1 Bias harus aligned dengan H4 direction)
        if pat_sentiment != "NEUTRAL" and pat_sentiment != direction:
             return {
                "valid": False, 
                "reason": f"H1 Context Conflict: User Pattern '{user_pattern}' ({pat_sentiment}) berlawanan dengan H1 Bias ({direction})"
            }

    # Jika lolos semua, status valid dan sertakan volatility status untuk Engine
    return {
        "valid": True,
        "direction": direction,
        "confidence": 0.80,
        "volatility": volatility
    }