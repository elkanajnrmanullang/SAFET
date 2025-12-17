import numpy as np
import pandas as pd
from typing import Dict, Any

from backend.core.config import config as core_config

class RiskEngine:
    def __init__(self, balance: float, risk_pct: float = 0.01):
        self.balance = float(balance)
        self.risk_pct = float(risk_pct)

    def calculate(self, entry: float, atr: float, direction: str, structure: Dict[str, float] = None) -> Dict[str, Any]:
        entry = float(entry)
        atr = float(atr)
        
        buffer = atr * core_config.ATR_MULTIPLIER_SL 

        sup = structure.get('support') if structure else (entry - atr * 1.5)
        res = structure.get('resistance') if structure else (entry + atr * 1.5)

        if direction.upper() == "LONG":
            sl_price = sup - buffer
            
            if sl_price >= entry: 
                sl_price = entry - (atr * 1.0) 
                
        elif direction.upper() == "SHORT":
            sl_price = res + buffer
            
            if sl_price <= entry: 
                sl_price = entry + (atr * 1.0) 
        else:
            sl_price = entry - (atr * 1.0)

        risk_dist = abs(entry - sl_price)
        
        if risk_dist == 0:
            risk_dist = entry * 0.01 

        rr_ratio = core_config.ATR_MULTIPLIER_TP 
        
        if direction.upper() == "LONG":
            tp_price = entry + (risk_dist * rr_ratio)
        else:
            tp_price = entry - (risk_dist * rr_ratio)

        risk_amount_usd = self.balance * self.risk_pct
        position_size = risk_amount_usd / risk_dist

        return {
            "entry": entry,
            "stop_loss": round(sl_price, 5),
            "take_profit": round(tp_price, 5),
            "position_size": round(position_size, 4),
            "risk_amount": round(risk_amount_usd, 2),
            "atr": atr,
            "rr_ratio": f"1:{rr_ratio:.1f} (Fixed)",
            "note": "SL @ Structure + 0.5 ATR Buffer"
        }

    def calc_volatility(self, df: pd.DataFrame) -> float:
        returns = df["close"].pct_change().dropna()
        return float(returns.std())