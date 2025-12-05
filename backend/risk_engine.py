# backend/risk_engine.py
"""
Risk Engine:
- Hitung SL/TP (volatility-aware)
- Position sizing
- Risk-reward optimization
"""

import numpy as np
import pandas as pd
from typing import Dict, Any


class RiskEngine:

    def calc_volatility(self, df: pd.DataFrame) -> float:
        returns = df["close"].pct_change().dropna()
        return float(returns.std())

    def dynamic_sl_tp(self, df: pd.DataFrame, direction: str) -> Dict[str, float]:
        vol = self.calc_volatility(df)

        # Crypto = volatile => gunakan faktor besar
        sl = vol * 1.8
        tp = vol * 3.5

        if direction == "short":
            sl, tp = tp, sl  # swap

        return {
            "sl_pct": float(sl),
            "tp_pct": float(tp)
        }

    def position_size(self, balance: float, risk_pct: float, sl_pct: float) -> float:
        # Manajemen risiko standar: %risk / SL distance
        amount = balance * risk_pct / max(sl_pct, 0.0001)
        return float(amount)

    def run(self, df: pd.DataFrame, direction: str, balance: float) -> Dict[str, Any]:
        v = self.dynamic_sl_tp(df, direction)
        sl = v["sl_pct"]
        tp = v["tp_pct"]

        size = self.position_size(balance, risk_pct=0.01, sl_pct=sl)

        return {
            "volatility": self.calc_volatility(df),
            "sl_pct": sl,
            "tp_pct": tp,
            "position_size": size,
            "suggestion": f"SL {sl:.3f}, TP {tp:.3f}, Size {size:.2f}"
        }


if __name__ == "__main__":
    import pandas as pd
    df = pd.DataFrame({
        "close": np.linspace(100, 105, 60) + np.random.randn(60)
    })
    r = RiskEngine()
    print(r.run(df, "long", 1000))
