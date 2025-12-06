"""
Risk Engine (Structure Based)
---------------------------------
Menghitung SL berdasarkan Invalidation Point (Support/Resistance)
dan memastikan Risk:Reward Ratio minimal 1:2.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any

class RiskEngine:
    def __init__(self, balance: float, risk_pct: float = 0.01):
        """
        Inisialisasi Risk Engine.
        """
        self.balance = float(balance)
        self.risk_pct = float(risk_pct)

    def calculate(self, entry: float, atr: float, direction: str, structure: Dict[str, float] = None) -> Dict[str, Any]:
        """
        Menghitung SL/TP Strategis.
        
        Logic SL (Invalidation):
        - SHORT: SL = Resistance + Buffer (Agar tidak kena stop hunt wicks)
        - LONG:  SL = Support - Buffer
        
        Logic TP (Ratio):
        - TP = Entry + (Jarak_SL * 2) -> Ratio 1:2 Fixed
        """
        entry = float(entry)
        atr = float(atr)
        
        # 1. Tentukan Buffer (Napas Tambahan)
        # Buffer menggunakan 0.5 ATR agar dinamis sesuai volatilitas saat itu
        buffer = atr * 0.5 

        # Ambil data support/resistance dari struktur market (jika ada)
        # Jika tidak ada (fallback), gunakan ATR multiplier standar
        sup = structure.get('support') if structure else (entry - atr * 1.5)
        res = structure.get('resistance') if structure else (entry + atr * 1.5)

        # 2. Hitung Harga Stop Loss (SL)
        if direction.upper() == "LONG":
            # SL di bawah Support
            sl_price = sup - buffer
            # Safety: Jangan sampai SL di atas harga entry (logic error)
            if sl_price >= entry: 
                sl_price = entry - (atr * 1.5)
                
        elif direction.upper() == "SHORT":
            # SL di atas Resistance
            sl_price = res + buffer
            # Safety: Jangan sampai SL di bawah harga entry
            if sl_price <= entry: 
                sl_price = entry + (atr * 1.5)
        else:
            sl_price = entry - (atr * 1.5) # Fallback

        # 3. Hitung Jarak Risiko (Risk Distance per Koin)
        risk_dist = abs(entry - sl_price)
        
        if risk_dist == 0:
            risk_dist = entry * 0.01 # Fallback 1% prevent division by zero

        # 4. Hitung Take Profit (TP) -> TARGET RATIO 1:2
        # Kita proyeksikan TP sejauh 2x jarak risiko
        if direction.upper() == "LONG":
            tp_price = entry + (risk_dist * 2.0)
        else:
            tp_price = entry - (risk_dist * 2.0)

        # 5. Position Sizing
        # Berapa lot yang dibeli agar jika kena SL, rugi = Risk Amount ($)
        risk_amount = self.balance * self.risk_pct
        position_size = risk_amount / risk_dist

        return {
            "entry": entry,
            "stop_loss": round(sl_price, 5),
            "take_profit": round(tp_price, 5),
            "position_size": round(position_size, 4),
            "risk_amount": round(risk_amount, 2),
            "atr": atr,
            "rr_ratio": "1:2.0 (Structure Based)",
            "note": "SL @ Structure Invalidation"
        }

    # --- Legacy Support ---
    def calc_volatility(self, df: pd.DataFrame) -> float:
        returns = df["close"].pct_change().dropna()
        return float(returns.std())