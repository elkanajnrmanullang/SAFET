# =============================
# FUNDAMENTAL ENGINE (RULE BASED)
# =============================

CRITICAL_KEYWORDS = [
    "sec lawsuit", "exchange hack", "stablecoin depeg",
    "protocol exploit", "network outage", "regulatory ban",
    "etf rejection"
]

HIGH_RISK = [
    "funding rate extreme", "oi spike",
    "liquidation cluster", "short squeeze", "long squeeze"
]

MACRO_EVENTS = [
    "fomc", "interest rate decision", "cpi",
    "nfp", "jobs report", "rate hike", "rate cut"
]


def analyze_fundamental(text):
    text = text.lower()

    reasons = []
    flag = "GREEN"
    action = "allow trade"

    for k in CRITICAL_KEYWORDS:
        if k in text:
            return {
                "flag": "RED",
                "reason": [k],
                "action": "NO TRADE"
            }

    for k in MACRO_EVENTS:
        if k in text:
            flag = "RED"
            reasons.append(k)

    for k in HIGH_RISK:
        if k in text:
            flag = "YELLOW"
            reasons.append(k)
            action = "reduce size"

    return {
        "flag": flag,
        "reason": reasons or ["no significant risk detected"],
        "action": action
    }

class FundamentalEngine:
    def evaluate(self, signals: list):
        level = "GREEN"
        action = "ALLOW_FULL"

        for s in signals:
            if s["impact"] == "critical":
                return {
                    "flag": "RED",
                    "action": "BLOCK",
                    "reason": s["keyword"]
                }

            if s["impact"] == "high":
                level = "YELLOW"
                action = "REDUCE_SIZE"

        return {
            "flag": level,
            "action": action,
            "reason": [s["keyword"] for s in signals]
        }
