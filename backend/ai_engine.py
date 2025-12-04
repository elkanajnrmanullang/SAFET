import json
import os

# ==============================
# LLM LAYER (DISABLED BY DESIGN)
# ==============================

# from openai import OpenAI

# client = OpenAI(
#     api_key=os.getenv("OPENAI_API_KEY"),
#     base_url=os.getenv("OPENAI_BASE_URL")
# )

MODEL = os.getenv("OPENAI_MODEL_NAME")

SYSTEM_PROMPT = """
You are AltaQuant Core.
Strict multi-timeframe auditor.
No guessing. No indicator invention.

RULES:
- 4H defines allowed direction.
- 1H must confirm 4H bias.
- 30M must show liquidity sweep + reclaim.
- 15M must show impulse + volume confirmation.
- FUNDAMENTAL RED overrides everything.

Output JSON ONLY.
"""

# ==============================
# CORE ENGINE (ACTIVE)
# ==============================

from backend.crypto_data import evaluate_technical
from backend.fundamental import FundamentalEngine
from backend.risk_engine import RiskEngine
from backend.blackout import EventBlackout


def final_decision(technical_data, fundamental_signals, equity, atr, entry_price):
    """
    MAIN DECISION ENGINE
    Deterministic, rule-based, backtestable
    """

    # 1️⃣ TECHNICAL FILTER
    technical = evaluate_technical(technical_data)
    if not technical["valid"]:
        return {
            "status": "NO_TRADE",
            "reason": technical["reason"]
        }

    # 2️⃣ FUNDAMENTAL FILTER
    fundamental = FundamentalEngine().evaluate(fundamental_signals)
    if fundamental["action"] == "BLOCK":
        return {
            "status": "BLOCKED_BY_FUNDAMENTAL",
            "detail": fundamental
        }

    # 3️⃣ EVENT BLACKOUT
    blackout = EventBlackout(
        events=technical_data.get("events", [])
    )
    if not blackout.is_allowed():
        return {
            "status": "EVENT_BLACKOUT",
            "reason": "+/- 60 minutes macro event"
        }

    # 4️⃣ RISK ENGINE
    risk_pct = 0.005 if fundamental["action"] == "REDUCE_SIZE" else 0.01
    risk = RiskEngine(equity, risk_pct).calculate(
        entry=entry_price,
        atr=atr,
        direction=technical["direction"]
    )

    # 5️⃣ FINAL OUTPUT
    return {
        "status": "EXECUTE",
        "direction": technical["direction"],
        "confidence": technical["confidence"],
        "risk": risk,
        "fundamental": fundamental
    }


# ==============================
# LEGACY PIPELINE (OPTIONAL)
# ==============================

def run_ai_pipeline(technical_data, fundamental_signals, equity, atr, entry_price):
    """
    Backward-compatible wrapper
    """

    return final_decision(
        technical_data=technical_data,
        fundamental_signals=fundamental_signals,
        equity=equity,
        atr=atr,
        entry_price=entry_price
    )
