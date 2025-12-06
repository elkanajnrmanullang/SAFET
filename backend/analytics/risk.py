"""
Risk Engine (Fixed for AltaQuant)
---------------------------------
Menangani perhitungan manajemen risiko, Position Sizing, dan SL/TP dinamis
berdasarkan ATR (Average True Range).
"""

import numpy as np
import pandas as pd
from typing import Dict, Any

class RiskEngine:
    def __init__(self, balance: float, risk_pct: float = 0.01):
        """
        Inisialisasi Risk Engine dengan saldo dan toleransi risiko.
        Dipanggil oleh engine.py sebagai: risk_engine = RiskEngine(equity, risk_pct)
        """
        self.balance = float(balance)
        self.risk_pct = float(risk_pct)

    def calculate(self, entry: float, atr: float, direction: str) -> Dict[str, Any]:
        """
        Menghitung Stop Loss, Take Profit, dan Ukuran Posisi berbasis ATR.
        Dipanggil oleh engine.py sebagai: risk_engine.calculate(...)
        """
        # Konfigurasi Multiplier (Risk Reward Ratio 1:2)
        # SL = 1.5 x ATR (Cukup lebar untuk napas)
        # TP = 3.0 x ATR (Target profit)
        sl_multiplier = 1.5
        tp_multiplier = 3.0

        entry = float(entry)
        atr = float(atr)

        # Hitung Harga SL & TP berdasarkan arah
        if direction.upper() == "LONG":
            sl_price = entry - (atr * sl_multiplier)
            tp_price = entry + (atr * tp_multiplier)
        elif direction.upper() == "SHORT":
            sl_price = entry + (atr * sl_multiplier)
            tp_price = entry - (atr * tp_multiplier)
        else:
            # Fallback (Safety)
            sl_price = entry - (atr * sl_multiplier)
            tp_price = entry + (atr * tp_multiplier)

        # Hitung Jarak SL (Distance)
        sl_distance = abs(entry - sl_price)
        
        # Safety Check: Hindari error pembagian nol
        if sl_distance == 0:
            sl_distance = entry * 0.01  # Fallback 1% dari harga entry

        # Hitung Risk Amount (Uang yang siap dirisikokan, misal $10 dari $1000)
        risk_amount = self.balance * self.risk_pct

        # Hitung Position Size (Unit Koin)
        # Rumus: Risk Amount ($) / Jarak SL per koin ($)
        # Contoh: Rela rugi $10. Jarak SL ke Entry $5. Maka beli 2 Koin.
        position_size = risk_amount / sl_distance

        return {
            "entry": entry,
            "stop_loss": round(sl_price, 5),
            "take_profit": round(tp_price, 5),
            "position_size": round(position_size, 4),
            "risk_amount": round(risk_amount, 2),
            "atr": atr,
            "rr_ratio": f"1:{tp_multiplier/sl_multiplier:.1f}"
        }

    # --- Legacy Support (Opsional: Mempertahankan fungsi lama jika ada modul lain yang butuh) ---
    def calc_volatility(self, df: pd.DataFrame) -> float:
        returns = df["close"].pct_change().dropna()
        return float(returns.std())