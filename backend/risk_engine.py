class RiskEngine:
    def __init__(self, equity: float, risk_pct: float = 0.01):
        self.equity = equity
        self.risk_pct = risk_pct

    def calculate(self, entry, atr, direction, atr_mult=1.2):
        risk_amount = self.equity * self.risk_pct
        stop_distance = atr * atr_mult
        position_size = risk_amount / stop_distance

        if direction == "LONG":
            sl = entry - stop_distance
            tp = entry + (stop_distance * 2)
        else:
            sl = entry + stop_distance
            tp = entry - (stop_distance * 2)

        return {
            "position_size": round(position_size, 4),
            "stop_loss": round(sl, 2),
            "take_profit": round(tp, 2),
            "rr": 2
        }
