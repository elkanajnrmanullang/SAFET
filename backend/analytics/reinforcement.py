import json
import numpy as np
from typing import Dict, Any


class ReinforcementLearner:

    def __init__(self):
        self.weights = {
            "pattern": 0.35,
            "anomaly": 0.15,
            "forecast": 0.45,
            "risk": 0.05
        }

    # UPDATE WEIGHT BASED ON OUTCOME
    def update(self, signal_context: Dict[str, Any], result: str):

        adj = 0.02 if result == "win" else -0.02

        for k in self.weights:
            if signal_context.get(k, None):
                self.weights[k] += adj

        # Normalisasi (sum to 1)
        total = sum(self.weights.values())
        for k in self.weights:
            self.weights[k] = max(0.01, self.weights[k] / total)

        return self.weights

    # SCORE SIGNAL
    def score_signal(self, ctx: Dict[str, Any]) -> float:
        p = ctx.get("pattern_conf", 0)
        a = 1 - ctx.get("anomaly_severity", 0)
        f = ctx.get("forecast_prob", 0)
        r = ctx.get("risk_score", 0)

        w = self.weights

        score = (
            p * w["pattern"] +
            a * w["anomaly"] +
            f * w["forecast"] +
            r * w["risk"]
        )

        return float(np.clip(score, 0, 1))


if __name__ == "__main__":
    rl = ReinforcementLearner()
    print("initial:", rl.weights)

    print("after win:", rl.update({"pattern": True}, "win"))
    print("score:", rl.score_signal({
        "pattern_conf": 0.7,
        "anomaly_severity": 0.1,
        "forecast_prob": 0.6,
        "risk_score": 0.8
    }))
