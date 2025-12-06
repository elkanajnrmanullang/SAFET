"""
Core decision engine (Simplified 3-TF Logic)
H4 Trend -> H1 Bias/Setup -> M15 Trigger
"""

from typing import Any, Dict, List, Optional
from backend.crypto.data import evaluate_technical
from backend.crypto.structure import detect_m15_execution
from backend.analytics.fundamental import FundamentalEngine
from backend.analytics.risk import RiskEngine
from backend.core.blackout import EventBlackout
from backend.analytics.anomaly import detect_anomaly

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
    # Fungsi ini mengecek H4 Trend dan H1 Alignment sekaligus
    tech_audit = evaluate_technical(technical_data)
    
    if not tech_audit.get("valid", False):
        return {
            "status": "NO_TRADE", 
            "reason": f"Tech Audit Failed: {tech_audit.get('reason')}", 
            "notes": notes
        }

    direction = tech_audit.get("direction")
    confidence = 0.75 # Start confidence lebih tinggi karena logic lebih simpel

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
    # STEP 4: M15 Execution Trigger (LANGSUNG DARI H1)
    # ------------------------------------------------------
    # Kita SKIP M30 Liquidity Sweep. H1 dianggap sebagai Setup Location.
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
    # STEP 5: Risk & Anomaly Final Check
    # ------------------------------------------------------
    anomaly = detect_anomaly(df_m15)
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

def run_ai_pipeline(technical_data, fundamental_signals, equity, entry_price, context_meta=None):
    atr = float(context_meta.get("atr", technical_data.get("atr", 0.0001)))
    return final_decision(technical_data, fundamental_signals, equity, atr, entry_price, context_meta)