"""
Core decision engine (AltaQuant 3-Layer Matrix)
Strategy Hierarchy:
1. Tier 1 (Sniper Elite): M30 Setup + M15 Trigger (High Prob, Full Risk)
2. Tier 2 (Assault): Super Trend (ADX > 35) + M15 Trigger (High Momentum, Full Risk)
3. Tier 3 (Guerrilla): No M30 Setup + M15 Local Reaction (Recovery, Reduced Risk)
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
    # 🛡️ STEP 0: THE GATEKEEPER (Global Filter)
    # ============================================================
    # Syarat Mutlak: H4 Trend Valid & H1 Bias Aligned & User Pattern Valid
    # Jika gagal di sini, tidak ada Tier yang boleh jalan.
    
    tech_audit = evaluate_technical(technical_data)
    
    if not tech_audit.get("valid", False):
        return {
            "status": "NO_TRADE", 
            "reason": f"Gatekeeper Blocked: {tech_audit.get('reason')}", 
            "notes": notes
        }

    direction = tech_audit.get("direction")
    base_confidence = 0.80 

    # ============================================================
    # 🛡️ STEP 0.5: EXTERNAL FILTERS
    # ============================================================
    # Cek Fundamental (Berita) & Event Blackout
    fundamental = FundamentalEngine().evaluate(fundamental_signals)
    if fundamental.get("action") == "BLOCK":
        return {"status": "BLOCKED_BY_FUNDAMENTAL", "detail": fundamental, "notes": notes}
    
    if fundamental.get("action") == "REDUCE_SIZE":
        notes.append("⚠️ Fundamental Warning (Size Reduced)")
        base_confidence -= 0.1

    event_times = technical_data.get("events", [])
    if not EventBlackout(events=event_times).is_allowed():
        return {"status": "EVENT_BLACKOUT", "reason": "Macro Event Window", "notes": notes}

    # ============================================================
    # ⚔️ STEP 1: STRATEGY MATRIX (THE WATERFALL)
    # ============================================================
    
    # A. Data Gathering
    trend_h4_data = technical_data.get("trend_h4", {})
    adx_val = float(trend_h4_data.get("adx", 0))
    
    df_m30 = technical_data.get("df_m30")
    # Cek M30 Zone/Liquidity (Syarat Tier 1)
    m30_setup = detect_liquidity_setup(df_m30, direction) 
    
    df_m15 = technical_data.get("df_m15")
    # Cek M15 Breakout/Bounce (Syarat Wajib Semua Tier)
    m15_exec = detect_m15_execution(df_m15, direction)    
    
    # Logic Variables
    is_super_trend = adx_val >= config.ADX_SUPER_TREND
    
    final_status = "WAITING"
    final_reason = "No Setup Matches Matrix"
    strategy_used = "None"
    structure_levels_for_risk = {}
    applied_risk_scale = 1.0

    # ------------------------------------------------------------
    # 🥇 TIER 1: THE SNIPER ELITE (Ideal Setup)
    # Syarat: M30 Zone/Sweep VALID + M15 Trigger VALID
    # ------------------------------------------------------------
    if m30_setup["valid"]:
        if m15_exec["valid"]:
            final_status = "EXECUTE"
            strategy_used = "Tier 1: Sniper Elite (M30 Sweep + M15 Trig)"
            notes.append(f"M30: {m30_setup.get('detail')}")
            notes.append(f"M15: {m15_exec.get('detail')}")
            # Sniper pakai level struktur M30 (lebih kuat)
            structure_levels_for_risk = m30_setup.get("levels") 
            applied_risk_scale = 1.0
        else:
            final_status = "WAIT_FOR_TRIGGER"
            final_reason = f"Tier 1 Active: M30 Ready ({m30_setup.get('detail')}), Waiting M15"
            notes.append(f"M30 Locked: {m30_setup.get('detail')}")

    # ------------------------------------------------------------
    # 🥈 TIER 2: THE ASSAULT (Momentum Bypass)
    # Syarat: Super Trend (ADX > 35) + M15 Trigger VALID
    # (M30 Setup di-bypass karena tren terlalu kencang)
    # ------------------------------------------------------------
    elif is_super_trend:
        if m15_exec["valid"]:
            final_status = "EXECUTE"
            strategy_used = "Tier 2: Assault (Super Trend Bypass)"
            notes.append(f"🚀 Super Trend (ADX {adx_val:.1f}). M30 Bypassed.")
            notes.append(f"M15: {m15_exec.get('detail')}")
            # Assault pakai level struktur M15 (karena M30 dilewati)
            structure_levels_for_risk = m15_exec.get("levels")
            applied_risk_scale = 1.0
            base_confidence -= 0.05 
        else:
            final_status = "WAIT_FOR_TRIGGER"
            final_reason = "Tier 2 Active: Super Trend, Waiting M15 Impulse"

    # ------------------------------------------------------------
    # 🥉 TIER 3: THE GUERRILLA (Local Reaction)
    # Syarat: M30 Gagal, Tren Normal (ADX > 20), TAPI M15 Reaksi Bagus
    # Risk: Reduced (70%)
    # ------------------------------------------------------------
    elif m15_exec["valid"]:
        # Gatekeeper sudah memastikan ADX > 20 dan Tren Valid
        final_status = "EXECUTE"
        strategy_used = "Tier 3: Guerrilla (Local Reaction Fallback)"
        notes.append("⚠️ M30 Zone Missed. Using Local M15 Reaction.")
        notes.append(f"M15: {m15_exec.get('detail')}")
        
        # Guerrilla pakai level lokal M15
        structure_levels_for_risk = m15_exec.get("levels")
        
        # SAFETY FIRST: Kurangi resiko sesuai Config
        applied_risk_scale = config.TIER_3_RISK_SCALE 
        base_confidence -= 0.15 

    else:
        # Jika Tier 1 gagal trigger, Tier 2 syarat ADX tak penuhi, Tier 3 M15 tak valid
        final_status = "WAIT_FOR_SETUP"
        final_reason = f"No Setup. (M30: {m30_setup.get('reason')}) (ADX: {adx_val:.1f})"

    # ============================================================
    # 📝 STEP 2: EXECUTION & SIZING
    # ============================================================
    
    if final_status == "EXECUTE":
        # 1. Anomaly Check (Pump/Dump Detector)
        anomaly = detect_anomaly(df_m15)
        if anomaly["anomaly"]:
            severity = anomaly["severity"]
            if severity >= 0.95:
                 return {"status": "NO_TRADE", "reason": "Severe Anomaly (Pump/Dump)", "anomaly": anomaly}
            base_confidence *= (1.0 - 0.4 * severity)
            notes.append(f"Anomaly severity {severity:.2f}")

        # 2. Risk Calculation
        base_risk_pct = config.RISK_PCT
        
        # Fundamental Modifier
        if fundamental.get("action") == "REDUCE_SIZE":
            base_risk_pct /= 2
        
        # Strategy Matrix Modifier (Apply Tier Scale)
        final_risk_pct = base_risk_pct * applied_risk_scale

        risk_engine = RiskEngine(equity, final_risk_pct)
        
        # Fallback Level jika structure kosong (seharusnya tidak terjadi jika structure.py benar)
        if not structure_levels_for_risk:
            structure_levels_for_risk = m15_exec.get("levels", {})

        risk_calc = risk_engine.calculate(
            entry=entry_price, 
            atr=atr, 
            direction=direction, 
            structure=structure_levels_for_risk
        )
        
        # Info tambahan di notes risiko
        if applied_risk_scale < 1.0:
            risk_calc["note"] += f" (Reduced Size: {applied_risk_scale*100:.0f}%)"

        return {
            "status": "EXECUTE",
            "direction": direction,
            "confidence": round(base_confidence, 2),
            "strategy": strategy_used,
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