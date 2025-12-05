from typing import List, Dict, Any

# ===========================
# KEYWORD DICTIONARIES
# ===========================

CRITICAL_KEYWORDS = {
    "etf approval": "critical",
    "etf rejection": "critical",
    "sec lawsuit": "critical",
    "exchange hack": "critical",
    "stablecoin depeg": "critical",
    "network outage": "critical",
    "protocol exploit": "critical",
    "regulatory ban": "critical",
}

# Gabungan High Risk & On-Chain (High Priority)
HIGH_RISK_KEYWORDS = {
    # Derivatives
    "funding rate extreme": "squeeze_risk",
    "oi spike": "squeeze_risk",
    "open interest spike": "squeeze_risk",
    "liquidation cluster": "squeeze_risk",
    "short squeeze": "squeeze_risk",
    "long squeeze": "squeeze_risk",
    
    # On-Chain Flow
    "exchange inflow": "high",
    "whale accumulation": "high",
    "whale distribution": "high",
    "token unlock": "high",
    "large inflow": "high",
}

MACRO_KEYWORDS = {
    "fomc": "macro",
    "interest rate decision": "macro",
    "cpi": "macro",
    "nfp": "macro",
    "jobs report": "macro",
    "rate hike": "macro",
    "rate cut": "macro",
    "inflation data": "macro",
}

class FundamentalEngine:
    def __init__(self):
        self.critical_map = CRITICAL_KEYWORDS
        self.high_risk_map = HIGH_RISK_KEYWORDS
        self.macro_map = MACRO_KEYWORDS

    def evaluate(self, signals: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not signals:
            return {"flag": "GREEN", "action": "ALLOW_FULL", "reason": ["no_signals"]}

        # 1. State Tracking
        has_critical = False
        has_macro = False
        
        # Squeeze Logic Tracking
        has_funding_extreme = False
        has_oi_spike = False
        
        reasons = []

        # 2. Scanning Loop
        for s in signals:
            kw = s.get("keyword", "").lower()
            impact = s.get("impact", "").lower()

            if kw in self.critical_map or impact == "critical":
                has_critical = True
                reasons.append(kw)

            if kw in self.macro_map or impact == "macro":
                has_macro = True
                reasons.append(kw)

            if "funding rate extreme" in kw:
                has_funding_extreme = True
            if "oi spike" in kw or "open interest spike" in kw:
                has_oi_spike = True
            
            if kw in self.high_risk_map:
                reasons.append(kw)

        # 3. Decision Logic
        
        # A. CRITICAL override everything
        if has_critical:
            return {"flag": "RED", "action": "BLOCK", "reason": reasons}

        # B. Squeeze Check (Combination Rule)
        if has_funding_extreme and has_oi_spike:
            return {
                "flag": "RED", 
                "action": "BLOCK", 
                "reason": ["High Squeeze Risk (Funding + OI Spike)"]
            }

        # C. Macro Check
        if has_macro:
            return {"flag": "YELLOW", "action": "REDUCE_SIZE", "reason": reasons}
            
        # D. Generic High Risk (On-chain, single derivative signal)
        if len(reasons) > 0:
             return {"flag": "YELLOW", "action": "REDUCE_SIZE", "reason": reasons}

        return {"flag": "GREEN", "action": "ALLOW_FULL", "reason": ["Clean"]}

    # Text analyzer helper (tetap sama, bisa update map reference)
    def analyze_text(self, text: str) -> Dict[str, Any]:
        # (Logika serupa dengan evaluate, disederhanakan untuk raw text)
        return self.evaluate([{"keyword": k} for k in text.lower().split() if k in {**self.critical_map, **self.high_risk_map, **self.macro_map}])