"""
backend/hedge_engine.py
SL/TP Engine + Exposure Protection
Bagian dari 70% AI Implementation Layer.
Mengelola smart stop loss, take profit, volatility-adjusted SL,
dan dynamic trailing.

Digunakan oleh:
- ai_engine.py (core decision-making)
- risk_engine.py (position size + leverage)
- reinforcement_loop.py (adaptive tuning)
"""

import numpy as np
from typing import Dict, Any


class HedgeEngine:

    def __init__(self):
        # Master preset (auto-adjust oleh reinforcement loop)
        self.min_sl_pct = 0.002        # default 0.2%
        self.max_sl_pct = 0.015        # default 1.5%
        self.min_tp_pct = 0.004        # default 0.4%
        self.max_tp_pct = 0.030        # default 3%

        # volatility multiplier
        self.vol_mult_low = 0.9
        self.vol_mult_high = 1.4

        # for trailing system
        self.trail_trigger_multiplier = 1.8
        self.trail_step_pct = 0.0012   # 0.12%

    def compute_volatility(self, closes):
        """ATR-lite volatility measurement (fast & efficient)."""
        if len(closes) < 10:
            return 0.003

        arr = np.array(closes[-20:])
        return float(np.std(arr) / np.mean(arr))

    def dynamic_sl_tp(self, side: str, price: float, closes: list) -> Dict[str, Any]:
        """
        Menghasilkan SL & TP adaptif berbasis volatilitas.
        side: "long" atau "short".
        """

        vol = self.compute_volatility(closes)

        # map volatility -> SL & TP range
        sl_pct = np.clip(vol * self.vol_mult_high, self.min_sl_pct, self.max_sl_pct)
        tp_pct = np.clip(vol * self.vol_mult_low * 2.2, self.min_tp_pct, self.max_tp_pct)

        if side == "long":
            sl = price * (1 - sl_pct)
            tp = price * (1 + tp_pct)
        else:
            sl = price * (1 + sl_pct)
            tp = price * (1 - tp_pct)

        return {
            "sl": round(float(sl), 6),
            "tp": round(float(tp), 6),
            "sl_pct": sl_pct,
            "tp_pct": tp_pct,
            "volatility": vol
        }

    def trailing_stop(self, side: str, entry: float, current: float, closes: list) -> Dict[str, Any]:
        """
        Trailing SL berbasis volatilitas dan profit trigger.
        aktif ketika profit > trail_trigger_multiplier * volatility
        """

        vol = self.compute_volatility(closes)

        profit_pct = (current - entry) / entry if side == "long" else (entry - current) / entry

        trigger = vol * self.trail_trigger_multiplier

        if profit_pct < trigger:
            return {"active": False, "trail_sl": None}

        # Hit trail stop
        step = self.trail_step_pct

        if side == "long":
            trail_sl = current * (1 - step)
        else:
            trail_sl = current * (1 + step)

        return {
            "active": True,
            "trail_sl": round(float(trail_sl), 6),
            "profit_pct": round(float(profit_pct), 6),
            "volatility": vol
        }

    def hedge_signal(self, side: str, entry_price: float, current_price: float, closes: list):
        """
        High-level interface untuk ai_engine.py
        Menghasilkan:
        - sl/tp adaptif
        - trailing decision
        - hedge protection (anti dump/pump)
        """

        base = self.dynamic_sl_tp(side, entry_price, closes)
        trail = self.trailing_stop(side, entry_price, current_price, closes)

        # Anti extreme-move hedge (mini circuit breaker internal)
        vol = base["volatility"]
        extreme_flag = vol > 0.018   # threshold agresif
        hedge_action = "NONE"

        if extreme_flag:
            hedge_action = "CUT_50%" if vol < 0.030 else "CUT_ALL"

        return {
            "dynamic": base,
            "trailing": trail,
            "extreme_protection": hedge_action,
            "volatility": base["volatility"]
        }


# quick self-test
if __name__ == "__main__":
    closes = [100, 101, 99, 102, 103, 101, 100, 104, 105, 103, 102, 101]
    hedge = HedgeEngine()
    
    print("SL/TP:", hedge.dynamic_sl_tp("long", 100, closes))
    print("Trailing:", hedge.trailing_stop("long", 100, 105, closes))
    print("Hedge Signal:", hedge.hedge_signal("long", 100, 105, closes))
