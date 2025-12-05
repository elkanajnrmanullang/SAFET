"""
Core decision engine that composes technical evaluation, fundamental checks,
event blackout and risk sizing into a final, deterministic decision.

This module is rule-based, deterministic, and backtestable.
It accepts the outputs from the technical pipeline (build_ai_context / evaluate_technical)
and fundamental signals, and returns a final decision ready for execution.
"""

from typing import Any, Dict, List, Optional
import os

# Import local modules (existing) — they must exist in backend/
from backend.crypto_data import evaluate_technical  # returns {"valid":bool, "direction":str, "confidence":float, ...}
from backend.fundamental import FundamentalEngine
from backend.risk_engine import RiskEngine
from backend.blackout import EventBlackout
from backend import anomaly_detection

# Configurable defaults
DEFAULT_RISK_FULL = 0.01   # 1% per trade
DEFAULT_RISK_REDUCED = 0.005  # 0.5% when fundamentals suggest reduction
EVENT_WINDOW_MINUTES = 60

def final_decision(
    technical_data: Dict[str, Any],
    fundamental_signals: List[Dict[str, Any]],
    equity: float,
    atr: float,
    entry_price: float,
    context_meta: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Determine final trading decision.

    Steps:
    1. Technical filter (must be valid)
    2. Fundamental evaluation (may block or reduce size)
    3. Event blackout check (+/- EVENT_WINDOW_MINUTES)
    4. Anomaly detection adjustment (reduce confidence or block)
    5. Risk sizing via RiskEngine
    6. Return deterministic decision dict

    Returns structure:
    {
        "status": "EXECUTE"|"NO_TRADE"|"BLOCKED_BY_FUNDAMENTAL"|"EVENT_BLACKOUT",
        "direction": "LONG"/"SHORT"/None,
        "confidence": float,
        "risk": {...} or None,
        "fundamental": {...},
        "notes": [...]
    }
    """
    notes = []
    # 1) Technical filter
    technical = evaluate_technical(technical_data)
    if not technical.get("valid", False):
        return {"status": "NO_TRADE", "reason": technical.get("reason", "Technical invalid"), "notes": []}

    direction = technical.get("direction")
    confidence = float(technical.get("confidence", 0.5))

    # 2) Fundamental filter
    fundamental = FundamentalEngine().evaluate(fundamental_signals)
    if fundamental.get("action") in ("BLOCK", "NO_TRADE"):
        return {"status": "BLOCKED_BY_FUNDAMENTAL", "detail": fundamental, "notes": notes}

    # 3) Blackout check (use event timestamps from technical_data if any)
    event_times = technical_data.get("events", [])
    blackout = EventBlackout(events=event_times, window_minutes=EVENT_WINDOW_MINUTES)
    if not blackout.is_allowed():
        return {"status": "EVENT_BLACKOUT", "reason": f"+/- {EVENT_WINDOW_MINUTES} minutes macro event", "notes": notes}

    # 4) Anomaly detection adjustment (if anomaly present, reduce confidence or block)
    # Use M15 / M30 frame if provided in context_meta or technical_data
    df_m15 = None
    if context_meta and "df_m15" in context_meta:
        df_m15 = context_meta["df_m15"]
    elif technical_data.get("m15_df") is not None:
        df_m15 = technical_data.get("m15_df")

    anomaly_info = anomaly_detection.detect_anomaly(df_m15) if df_m15 is not None else {"anomaly": False}
    if anomaly_info.get("anomaly"):
        severity = float(anomaly_info.get("severity", 0.5))
        # if severity very high, block trade
        if severity >= 0.95:
            notes.append(f"Blocked due to severe anomaly: {anomaly_info}")
            return {"status": "NO_TRADE", "reason": "Severe anomaly detected", "anomaly": anomaly_info, "notes": notes}
        # otherwise, penalize confidence
        old_conf = confidence
        confidence = confidence * (1.0 - 0.4 * severity)  # reduce up to 40% based on severity
        notes.append(f"Anomaly detected, confidence {old_conf:.2f}->{confidence:.2f} (severity={severity:.2f})")

    # 5) Adjust risk % based on fundamental advice
    risk_pct = DEFAULT_RISK_FULL
    if fundamental.get("action") in ("REDUCE_SIZE", "reduce_size"):
        risk_pct = DEFAULT_RISK_REDUCED
        notes.append("Fundamental signals recommend reduced size")

    # 6) Risk sizing
    risk_engine = RiskEngine(equity, risk_pct)
    risk = risk_engine.calculate(entry=entry_price, atr=atr, direction=direction)

    # 7) Compose final output
    decision = {
        "status": "EXECUTE",
        "direction": direction,
        "confidence": round(confidence, 4),
        "risk": risk,
        "fundamental": fundamental,
        "anomaly": anomaly_info,
        "notes": notes
    }
    return decision


def run_ai_pipeline(
    technical_data: Dict[str, Any],
    fundamental_signals: List[Dict[str, Any]],
    equity: float,
    entry_price: float,
    context_meta: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Backward-compatible wrapper that extracts ATR from technical_data/context.
    """
    atr = None
    # Prefer explicit ATR from context_meta or technical_data
    if context_meta and "atr" in context_meta:
        atr = float(context_meta["atr"])
    else:
        # try technical_data
        atr = float(technical_data.get("atr", 0.0))
    if atr <= 0:
        # fallback: small epsilon to avoid division by zero
        atr = 0.0001

    return final_decision(
        technical_data=technical_data,
        fundamental_signals=fundamental_signals,
        equity=equity,
        atr=atr,
        entry_price=entry_price,
        context_meta=context_meta
    )


# Simple self-test when run directly (will not call external APIs)
if __name__ == "__main__":
    # dummy example
    technical_data_example = {"trend": {"valid": True, "direction": "LONG"}, "confidence": 0.85}
    fundamental_signals_example = [{"keyword": "funding rate extreme", "impact": "high", "action": "REDUCE_SIZE"}]
    dec = run_ai_pipeline(technical_data_example, fundamental_signals_example, equity=10000, entry_price=42000, context_meta={"atr": 50})
    print(dec)
