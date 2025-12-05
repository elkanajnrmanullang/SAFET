"""
Core decision engine (Waterfall Logic)
H4 Trend -> H1 Bias -> Fundamental -> M30 Setup -> M15 Trigger
"""

from typing import Any, Dict, List, Optional
from backend.crypto_data import evaluate_technical
from backend.mini_choch import detect_liquidity_setup, detect_m15_execution
from backend.fundamental import FundamentalEngine
from backend.risk_engine import RiskEngine
from backend.blackout import EventBlackout
from backend import anomaly_detection

DEFAULT_RISK_FULL = 0.01 
DEFAULT_RISK_REDUCED = 0.005 
EVENT_WINDOW_MINUTES = 60

def final_decision(
    technical_data: Dict[str, Any],
    fundamental_signals: List[Dict[str, Any]],
    equity: float,
    atr: float,
    entry_price: float,
    context_meta: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    
    notes = []
    
    # ------------------------------------------------------
    # STEP 1: H4 Anchor & H1 Bias (Technical Audit)
    # ------------------------------------------------------
    tech_audit = evaluate_technical(technical_data)
    if not tech_audit.get("valid", False):
        return {
            "status": "NO_TRADE", 
            "reason": f"Tech Audit Failed: {tech_audit.get('reason')}", 
            "notes": notes
        }

    direction = tech_audit.get("direction")
    confidence = 0.70 # Start base confidence

    # ------------------------------------------------------
    # STEP 2: Fundamental Gatekeeper
    # ------------------------------------------------------
    fundamental = FundamentalEngine().evaluate(fundamental_signals)
    if fundamental.get("action") == "BLOCK":
        return {
            "status": "BLOCKED_BY_FUNDAMENTAL", 
            "detail": fundamental, 
            "notes": notes
        }
    
    if fundamental.get("action") == "REDUCE_SIZE":
        notes.append("Fundamental warning: Size reduced.")

    # ------------------------------------------------------
    # STEP 3: Event Blackout
    # ------------------------------------------------------
    event_times = technical_data.get("events", [])
    if not EventBlackout(events=event_times, window_minutes=EVENT_WINDOW_MINUTES).is_allowed():
        return {"status": "EVENT_BLACKOUT", "reason": "Macro Event Window", "notes": notes}

    # ------------------------------------------------------
    # STEP 4: M30 Liquidity Setup
    # ------------------------------------------------------
    df_m30 = technical_data.get("df_m30")
    m30_setup = detect_liquidity_setup(df_m30, direction)
    
    if not m30_setup["valid"]:
        # Strict rule: No Liquidity Sweep = No Trade
        return {
            "status": "NO_TRADE", 
            "reason": f"M30 Setup Failed: {m30_setup.get('reason')}",
            "notes": notes
        }
    notes.append(f"M30: {m30_setup.get('detail')}")

    # ------------------------------------------------------
    # STEP 5: M15 Execution Trigger
    # ------------------------------------------------------
    df_m15 = technical_data.get("df_m15")
    m15_exec = detect_m15_execution(df_m15, direction)
    
    if not m15_exec["valid"]:
        return {
            "status": "WAIT_FOR_TRIGGER", 
            "reason": f"M15 Trigger Failed: {m15_exec.get('reason')}",
            "notes": notes
        }
    notes.append(f"M15: {m15_exec.get('detail')}")

    # ------------------------------------------------------
    # STEP 6: Risk & Anomaly Final Check
    # ------------------------------------------------------
    anomaly = anomaly_detection.detect_anomaly(df_m15)
    if anomaly["anomaly"]:
        severity = anomaly["severity"]
        if severity >= 0.95:
             return {"status": "NO_TRADE", "reason": "Severe Anomaly", "anomaly": anomaly}
        confidence *= (1.0 - 0.4 * severity)
        notes.append(f"Anomaly severity {severity:.2f}")

    # Risk Sizing
    risk_pct = DEFAULT_RISK_REDUCED if fundamental.get("action") == "REDUCE_SIZE" else DEFAULT_RISK_FULL
    risk_engine = RiskEngine(equity, risk_pct)
    risk_calc = risk_engine.calculate(entry=entry_price, atr=atr, direction=direction)

    return {
        "status": "EXECUTE",
        "direction": direction,
        "confidence": round(confidence, 2),
        "risk": risk_calc,
        "fundamental": fundamental,
        "notes": notes
    }

# (Fungsi wrapper run_ai_pipeline tetap sama, tidak perlu diubah)
def run_ai_pipeline(technical_data, fundamental_signals, equity, entry_price, context_meta=None):
    atr = float(context_meta.get("atr", technical_data.get("atr", 0.0001)))
    return final_decision(technical_data, fundamental_signals, equity, atr, entry_price, context_meta)