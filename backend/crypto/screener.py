import pandas as pd
import pandas_ta as ta
from backend.crypto.data import fetch_market_data # Update import path

class CryptoScreener:

    def __init__(self):
        # Tidak butuh init list di sini agar fleksibel dipanggil per koin
        pass

    # ====================================================
    # CORE LOGIC (Diadaptasi dari kode Anda)
    # ====================================================
    def run_screen(self, symbol: str, fundamental_data: list = None) -> dict:
        """
        Menjalankan Screening Tahap 0 pada satu simbol.
        Output disesuaikan agar bisa dibaca UI AltaQuant.
        """
        
        # 1. FETCH DATA
        # Kita pakai 1h sesuai request Anda, limit 200 cukup
        df = fetch_market_data(symbol, "1h", limit=200)
        
        # Return Fail jika data kosong
        if df is None or len(df) < 150:
            return {
                "symbol": symbol,
                "status": "FAIL",
                "details": {},
                "reasons": ["Insufficient Data"]
            }

        # 2. PREPARE INDICATORS
        # ATR
        df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=14)
        df["atr_pct"] = (df["atr"] / df["close"]) * 100
        
        # EMA & ADX
        df["ema50"] = ta.ema(df["close"], length=50)
        df["ema200"] = ta.ema(df["close"], length=200)
        adx = ta.adx(df["high"], df["low"], df["close"], length=14)
        if adx is not None:
             df["adx"] = adx["ADX_14"]
        else:
             df["adx"] = 0

        # Volume MA
        df["vol_ma"] = df["volume"].rolling(20).mean()
        
        # --- LOGIC VARIABLES ---
        last = df.iloc[-1]
        price = last["close"]
        atr_now = last["atr_pct"]
        adx_now = last["adx"]
        vol_ma = last["vol_ma"]
        
        # Hitung Volume dalam USDT (PENTING AGAR ADIL ANTARA BTC & SHIB)
        vol_usdt = vol_ma * price 

        checks = {}
        fail_reasons = []

        # ====================================================
        # RULE 1: MARKET HEALTH (Volatility & Price)
        # ====================================================
        # Filter shitcoin (Harga < 0.00001 misal, atau rule volatility)
        
        # Rule Volatility Anda: 0.2 < ATR < 15
        if atr_now < 0.2:
            checks["Volatility"] = f"FAIL ({atr_now:.2f}%)"
            fail_reasons.append("Market Dead/Flat (<0.2%)")
        elif atr_now > 15:
            checks["Volatility"] = f"FAIL ({atr_now:.2f}%)"
            fail_reasons.append("Extreme Volatility (>15%)")
        else:
            checks["Volatility"] = f"PASS ({atr_now:.2f}%)"

        # ====================================================
        # RULE 2: Volume (Volume USDT)
        # ====================================================
        # Kita pakai threshold misal $500,000 per jam rata-rata
        min_usdt_vol = 500_000 
        
        if vol_usdt < min_usdt_vol:
            checks["Volume"] = "FAIL"
            fail_reasons.append(f"Low Volume (${vol_usdt/1000:.0f}k < $500k)")
        else:
            checks["Volume"] = "PASS"
            
        # ====================================================
        # RULE 3: TREND PRE-FILTER (ADX)
        # ====================================================
        # Rule Anda: ADX minimal 15
        if adx_now < 15:
            checks["Trend_Potential"] = f"FAIL (ADX {adx_now:.1f})"
            fail_reasons.append("Choppy Market (ADX < 15)")
        else:
            checks["Trend_Potential"] = f"PASS (ADX {adx_now:.1f})"

        # ====================================================
        # RULE 4: STRUCTURE / NOISE (Tambahan dari Spec)
        # ====================================================
        # Cek apakah harga di atas EMA200 (Opsional, tapi bagus untuk screening long)
        # Di sini kita buat netral: Structure PASS asal tidak flat
        high_20 = df["high"].tail(20).max()
        low_20 = df["low"].tail(20).min()
        range_pct = (high_20 - low_20) / low_20 * 100
        
        if range_pct < 1.0:
            checks["Structure"] = "FAIL"
            fail_reasons.append("Price Flat (<1% Range)")
        else:
            checks["Structure"] = "PASS"

        # ====================================================
        # FINAL VERDICT
        # ====================================================
        # Lulus jika TIDAK ADA fail_reasons
        if len(fail_reasons) > 0:
            status = "FAIL"
        else:
            status = "PASS"

        return {
            "symbol": symbol,
            "status": status,
            "details": checks,
            "reasons": fail_reasons
        }