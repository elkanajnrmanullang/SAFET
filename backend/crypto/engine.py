"""
Core decision engine (AltaQuant 3-Layer Defense)
Strategy Hierarchy:
1. Tier 1 (Perfect): H4+H1+M30+M15 (The Standard)
2. Tier 2 (Momentum): H4+H1+M15 (Super Trend Bypass)
3. Tier 3 (Reaction): H4+H1+M15 (Local SnR/SnD Bounce/Breakout Fallback)
"""

from typing import Any, Dict, List, Optional
from backend.crypto.data import evaluate_technical
from backend.crypto.structure import detect_m15_execution, detect_liquidity_setup
from backend.analytics.fundamental import FundamentalEngine
from backend.analytics.risk import RiskEngine
from backend.core.blackout import EventBlackout
from backend.analytics.anomaly import detect_anomaly
from backend.core.config import config

def final_decision(
    technical_data: Dict[str, Any],
    fundamental_signals: List[Dict[str, Any]],
    equity: float,
    atr: float,
    entry_price: float,
    context_meta: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    
    notes = []
    
    # ============================================================
    # STEP 1: GLOBAL FILTER (H4 Anchor & H1 Bias) - WAJIB LULUS
    # ============================================================
    # Ini adalah "Gerbang Utama". Jika trend besar tidak mendukung, 
    # tidak ada metode apapun (1, 2, atau 3) yang boleh jalan.
    tech_audit = evaluate_technical(technical_data)
    
    if not tech_audit.get("valid", False):
        return {
            "status": "NO_TRADE", 
            "reason": f"Global Filter Failed: {tech_audit.get('reason')}", 
            "notes": notes
        }

    direction = tech_audit.get("direction")
    confidence = 0.80 # Base confidence awal

    # ============================================================
    # STEP 2: FUNDAMENTAL & EVENT FILTER
    # ============================================================
    fundamental = FundamentalEngine().evaluate(fundamental_signals)
    if fundamental.get("action") == "BLOCK":
        return {
            "status": "BLOCKED_BY_FUNDAMENTAL", 
            "detail": fundamental, 
            "notes": notes
        }
    
    if fundamental.get("action") == "REDUCE_SIZE":
        notes.append("Fundamental warning: Size reduced.")
        confidence -= 0.1

    event_times = technical_data.get("events", [])
    if not EventBlackout(events=event_times).is_allowed():
        return {"status": "EVENT_BLACKOUT", "reason": "Macro Event Window", "notes": notes}

    # ============================================================
    # STEP 3: ANALISA MIKRO (STRATEGY SELECTION MATRIX)
    # ============================================================
    
    # A. Data Gathering
    trend_h4_data = technical_data.get("trend_h4", {})
    adx_val = trend_h4_data.get("adx", 0)
    
    df_m30 = technical_data.get("df_m30")
    m30_setup = detect_liquidity_setup(df_m30, direction) # Cek Zone/Sweep
    
    df_m15 = technical_data.get("df_m15")
    m15_exec = detect_m15_execution(df_m15, direction)    # Cek Breakout/Bounce
    
    # Thresholds
    IS_SUPER_TREND = adx_val >= 35.0
    
    # B. Decision Logic (3 Metode Saling Membantu)
    final_status = "WAITING"
    final_reason = "No Valid Setup Found"
    strategy_used = "None"
    structure_levels = {}

    # --- METODE 1: STRICT WATERFALL (The Perfect Setup) ---
    if m30_setup["valid"]:
        if m15_exec["valid"]:
            final_status = "EXECUTE"
            strategy_used = "Tier 1: Structural Setup (M30+M15)"
            notes.append(f"M30: {m30_setup.get('detail')}")
            notes.append(f"M15: {m15_exec.get('detail')}")
            structure_levels = m30_setup.get("levels") # Prioritas level M30
        else:
            final_status = "WAIT_FOR_TRIGGER"
            final_reason = f"M30 Ready ({m30_setup.get('detail')}), Waiting M15 Trigger"
            notes.append(f"M30: {m30_setup.get('detail')}")

    # --- METODE 2: MOMENTUM BYPASS (The Fast Lane) ---
    elif IS_SUPER_TREND:
        if m15_exec["valid"]:
            final_status = "EXECUTE"
            strategy_used = "Tier 2: Momentum Bypass (Super Trend)"
            notes.append(f"⚠️ M30 Skipped (ADX {adx_val:.1f} > 35)")
            notes.append(f"M15: {m15_exec.get('detail')}")
            structure_levels = m15_exec.get("levels") # Pakai level M15 karena M30 skip
            confidence -= 0.05 # Sedikit diskon karena skip M30
        else:
            final_status = "WAIT_FOR_TRIGGER"
            final_reason = "Super Trend Active, Waiting M15 Trigger"

    # --- METODE 3: SnR/SnD REACTION FALLBACK (The Guerilla) ---
    # Jika M30 gagal & Tren tidak super kuat, TAPI harga bereaksi di level lokal M15
    elif m15_exec["valid"]:
        # Pastikan ini bukan "False Signal" di pasar mati
        # Syarat tambahan: Minimal ADX H4 > 20 (sudah lolos di step 1) 
        # dan M15 volume valid
        
        final_status = "EXECUTE"
        strategy_used = "Tier 3: Local SnR/SnD Reaction"
        notes.append("⚠️ M30 Zone Missed, using Local M15 Levels")
        notes.append(f"M15: {m15_exec.get('detail')}")
        structure_levels = m15_exec.get("levels")
        confidence -= 0.15 # Diskon confidence lebih besar karena tanpa M30 Zone
    
    else:
        # Jika ketiga metode gagal
        final_status = "WAIT_FOR_SETUP"
        final_reason = f"No M30 Setup, No Super Trend, No Local Trigger. (M30: {m30_setup.get('reason')})"

    # ============================================================
    # STEP 4: FINAL CHECK & RISK SIZING
    # ============================================================
    
    if final_status == "EXECUTE":
        # Cek Anomali Akhir
        anomaly = detect_anomaly(df_m15)
        if anomaly["anomaly"]:
            severity = anomaly["severity"]
            if severity >= 0.95:
                 return {"status": "NO_TRADE", "reason": "Severe Anomaly (Pump/Dump)", "anomaly": anomaly}
            confidence *= (1.0 - 0.4 * severity)
            notes.append(f"Anomaly severity {severity:.2f}")

        # Risk Calculation
        risk_pct = config.RISK_PCT
        if fundamental.get("action") == "REDUCE_SIZE":
            risk_pct /= 2
        
        # Adjust risk berdasarkan Tier Strategy
        if "Tier 3" in strategy_used:
            risk_pct *= 0.7 # Kurangi size untuk setup Tier 3 (High Risk)

        risk_engine = RiskEngine(equity, risk_pct)
        
        # Pastikan kita punya level struktur (Support/Resistance)
        final_levels = structure_levels if structure_levels else m15_exec.get("levels", {})

        risk_calc = risk_engine.calculate(
            entry=entry_price, 
            atr=atr, 
            direction=direction, 
            structure=final_levels
        )

        return {
            "status": "EXECUTE",
            "direction": direction,
            "confidence": round(confidence, 2),
            "strategy": strategy_used, # Info strategi untuk UI
            "risk": risk_calc,
            "fundamental": fundamental,
            "notes": notes
        }

    # Return Waiting Status
    return {
        "status": final_status,
        "reason": final_reason,
        "notes": notes
    }

def run_ai_pipeline(technical_data, fundamental_signals, equity, entry_price, context_meta=None):
    atr = float(context_meta.get("atr", technical_data.get("atr", 0.0001)))
    return final_decision(technical_data, fundamental_signals, equity, atr, entry_price, context_meta)