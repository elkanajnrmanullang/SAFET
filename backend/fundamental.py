"""
FundamentalEngine maps fundamental signals into standardized trading constraints:
(flag, action, reason)

Output consumed by ai_engine reinforcement + risk layering.

Supported sources:
- Raw news text
- Cryptopanic processed events
- Structured signals (keyword, category, impact)
"""

from typing import List, Dict, Any

# ===========================
# FUNDAMENTAL DICTIONARIES
# ===========================

CRITICAL_KEYWORDS = {
    "etf approval": "critical",
    "etf rejection": "critical",
    "sec lawsuit": "critical",
    "exchange hack": "critical",
    "stablecoin depeg": "critical",
    "network outage": "critical",
    "protocol exploit": "critical",
}

HIGH_RISK_KEYWORDS = {
    "funding rate extreme": "high",
    "oi spike": "high",
    "open interest spike": "high",
    "liquidation cluster": "high",
    "short squeeze": "high",
    "long squeeze": "high",
}

MACRO_KEYWORDS = {
    "fomc": "macro",
    "interest rate decision": "macro",
    "cpi": "macro",
    "nfp": "macro",
    "jobs report": "macro",
    "rate hike": "macro",
    "rate cut": "macro",
}

# ===========================
# FUNDAMENTAL ENGINE
# ===========================

class FundamentalEngine:
    def __init__(self):
        self.critical_map = CRITICAL_KEYWORDS
        self.high_risk_map = HIGH_RISK_KEYWORDS
        self.macro_map = MACRO_KEYWORDS

    # -------------------------------------------------------------
    # TEXT ANALYZER: FREEFORM NEWS/TWEETS TEXT
    # -------------------------------------------------------------
    def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        Lightweight free-text scanner. Converts raw text into:
        {flag, action, reason}
        """

        text_l = (text or "").lower()
        detected = []

        # CRITICAL FIRST → hard block
        for k in self.critical_map:
            if k in text_l:
                return {
                    "flag": "RED",
                    "action": "BLOCK",
                    "reason": [k]
                }

        # MACRO → generally medium severity
        for k in self.macro_map:
            if k in text_l:
                detected.append({"keyword": k, "impact": "macro"})

        # HIGH RISK → derivatives signal
        for k in self.high_risk_map:
            if k in text_l:
                detected.append({"keyword": k, "impact": "high"})

        # default evaluation
        if not detected:
            return {
                "flag": "GREEN",
                "action": "ALLOW_FULL",
                "reason": ["no_significant_fundamental"]
            }

        # If any macro
        if any(d["impact"] == "macro" for d in detected):
            return {
                "flag": "YELLOW",
                "action": "REDUCE_SIZE",
                "reason": [d["keyword"] for d in detected]
            }

        # If any high-risk derivatives signal
        if any(d["impact"] == "high" for d in detected):
            return {
                "flag": "YELLOW",
                "action": "REDUCE_SIZE",
                "reason": [d["keyword"] for d in detected]
            }

        return {
            "flag": "GREEN",
            "action": "ALLOW_FULL",
            "reason": ["fallback_no_detect"]
        }

    # -------------------------------------------------------------
    # STRUCTURED SIGNAL EVALUATOR
    # -------------------------------------------------------------
    def evaluate(self, signals: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Expected signals example:
        [
            {"keyword": "fomc", "impact": "macro"},
            {"keyword": "funding rate extreme", "impact": "high"}
        ]
        """

        if not signals:
            return {"flag": "GREEN", "action": "ALLOW_FULL", "reason": ["no_signals"]}

        final_flag = "GREEN"
        final_action = "ALLOW_FULL"
        reasons = []

        for s in signals:
            keyword = s.get("keyword", "").lower()
            impact = s.get("impact", "").lower()

            # CRITICAL → immediate override
            if keyword in self.critical_map or impact == "critical":
                return {
                    "flag": "RED",
                    "action": "BLOCK",
                    "reason": [keyword or "critical_signal"]
                }

            # MACRO EVENT
            if keyword in self.macro_map or impact == "macro":
                final_flag = "YELLOW"
                final_action = "REDUCE_SIZE"
                reasons.append(keyword or "macro_event")

            # HIGH RISK (derivatives)
            if keyword in self.high_risk_map or impact == "high":
                final_flag = "YELLOW"
                final_action = "REDUCE_SIZE"
                reasons.append(keyword or "high_risk_event")

            # fallback: any high-impact non-mapped event
            if impact in {"medium"}:
                final_flag = "YELLOW"
                final_action = "REDUCE_SIZE"
                reasons.append(keyword or "medium_impact_signal")

        return {
            "flag": final_flag,
            "action": final_action,
            "reason": reasons or ["no_specific_reason"]
        }


# Quick test
if __name__ == "__main__":
    engine = FundamentalEngine()
    print(engine.analyze_text("Breaking: funding rate extreme and oi spike detected"))
    print(engine.evaluate([{"keyword": "funding rate extreme", "impact": "high"}]))
