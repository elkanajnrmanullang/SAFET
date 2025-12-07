"""
Risk Engine (Structure Based)
---------------------------------
Menghitung SL berdasarkan Invalidation Point (Support/Resistance)
Rule:
1. SL = Structure Level +/- (0.5 * ATR)
2. TP = Fixed Risk:Reward 1:2
"""

import numpy as np
import pandas as pd
from typing import Dict, Any

class RiskEngine:
    def __init__(self, balance: float, risk_pct: float = 0.01):
        self.balance = float(balance)
        self.risk_pct = float(risk_pct)

    def calculate(self, entry: float, atr: float, direction: str, structure: Dict[str, float] = None) -> Dict[str, Any]:
        """
        Menghitung SL/TP Strategis sesuai dokumen.
        """
        entry = float(entry)
        atr = float(atr)
        
        # 1. Tentukan Buffer (Napas Tambahan)
        # WAJIB: Invalidation Point + 0.5 ATR
        buffer = atr * 0.5 

        # Ambil level struktur dari M30/M15 (yang dikirim dari engine.py)
        # Fallback jika struktur gagal terdeteksi: Pakai 1.5 ATR (standard swing)
        sup = structure.get('support') if structure else (entry - atr * 1.5)
        res = structure.get('resistance') if structure else (entry + atr * 1.5)

        # 2. Hitung Harga Stop Loss (SL)
        if direction.upper() == "LONG":
            # SL = Support - Buffer
            sl_price = sup - buffer
            
            # Safety Check: SL tidak boleh di atas Entry (Fatal logic error)
            if sl_price >= entry: 
                sl_price = entry - (atr * 1.0) # Fallback darurat
                
        elif direction.upper() == "SHORT":
            # SL = Resistance + Buffer
            sl_price = res + buffer
            
            # Safety Check: SL tidak boleh di bawah Entry
            if sl_price <= entry: 
                sl_price = entry + (atr * 1.0) # Fallback darurat
        else:
            sl_price = entry - (atr * 1.0)

        # 3. Hitung Jarak Risiko (Risk Distance per Koin)
        risk_dist = abs(entry - sl_price)
        
        if risk_dist == 0:
            risk_dist = entry * 0.01 # Prevent division by zero

        # 4. Hitung Take Profit (TP) -> TARGET FIXED RATIO 1:2
        if direction.upper() == "LONG":
            tp_price = entry + (risk_dist * 2.0)
        else:
            tp_price = entry - (risk_dist * 2.0)

        # 5. Position Sizing
        risk_amount_usd = self.balance * self.risk_pct
        position_size = risk_amount_usd / risk_dist

        return {
            "entry": entry,
            "stop_loss": round(sl_price, 5),
            "take_profit": round(tp_price, 5),
            "position_size": round(position_size, 4),
            "risk_amount": round(risk_amount_usd, 2),
            "atr": atr,
            "rr_ratio": "1:2.0 (Fixed)",
            "note": "SL @ Structure + 0.5 ATR Buffer"
        }

    # Helper volatility calculation
    def calc_volatility(self, df: pd.DataFrame) -> float:
        returns = df["close"].pct_change().dropna()
        return float(returns.std())