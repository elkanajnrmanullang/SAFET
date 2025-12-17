from typing import Any, Dict, List
from backend.crypto.data import evaluate_technical
from backend.crypto.structure import analyze_structure_context, detect_liquidity_grab
from backend.analytics.indicators import detect_fvg_zone
from backend.analytics.fundamental import FundamentalEngine
from backend.analytics.risk import RiskEngine
from backend.core.config import config

def final_decision(
    technical_data: Dict[str, Any],
    fundamental_signals: List[Dict[str, Any]],
    equity: float,
    atr: float,
    entry_price: float,
    context_meta: Dict[str, Any] = None
) -> Dict[str, Any]:
    
    notes = []
    
    # Data Unpacking
    df_h1 = technical_data.get("df_h1") 
    df_m30 = technical_data.get("df_m30")
    df_m15 = technical_data.get("df_m15")
    
    # Analisis Struktur Dasar
    struct = analyze_structure_context(df_m30, df_m15, df_h1)
    trend_h1 = struct['trend_h1']
    direction = "LONG" if trend_h1 == "UP" else "SHORT"
    
    # Deteksi Tambahan
    fvg = detect_fvg_zone(df_m15, direction)
    is_liq_grab, grab_level = detect_liquidity_grab(df_m15, direction)
    
    status = "WAIT_FOR_SETUP"
    scenario = "None"
    risk_calc = {}
    
    # SKENARIO 1: CONTINUOUS TREND DENGAN CHART PATTERN
    if struct['pattern_h1'] != "NONE":
        valid_pat = (trend_h1 == "UP" and "BULLISH" in struct['pattern_h1']) or \
                    (trend_h1 == "DOWN" and "BEARISH" in struct['pattern_h1'])
                    
        if valid_pat:
            status = "EXECUTE"
            scenario = "Skenario 1: Continuous Trend + Chart Pattern"
            notes.append(f"H1 Pattern: {struct['pattern_h1']}")
            
            sl_price = entry_price - (atr * 1.5) if direction == "LONG" else entry_price + (atr * 1.5)
            tp_price = entry_price + (abs(entry_price - sl_price) * 2) if direction == "LONG" else entry_price - (abs(entry_price - sl_price) * 2)
            
            risk_calc = {
                "entry": entry_price, "stop_loss": sl_price, "take_profit": tp_price,
                "position_size": 1.0, "risk_amount": equity * config.RISK_PCT, "note": "SL 10 Poin Rule"
            }
            return _pack_result(status, direction, scenario, risk_calc, notes)

    # SKENARIO 2: CONTINUOUS TREND DENGAN SnR
    if struct['snr_status'] in ["STRONG", "INTERMEDIATE"]:
        dist_to_snr = abs(entry_price - struct['snr_level'])
        if dist_to_snr <= (atr * 0.5): 
            if struct['is_weakening']:
                status = "EXECUTE"
                scenario = "Skenario 2: Continuous Trend + SnR"
                notes.append(f"Bounce on {struct['snr_status']} SnR + Weakening")
                
                risk_engine = RiskEngine(equity, config.RISK_PCT)
                risk_calc = risk_engine.calculate(entry_price, atr, direction, 
                                                structure={"support": struct['snr_level'], "resistance": struct['snr_level']})
                return _pack_result(status, direction, scenario, risk_calc, notes)

    # SKENARIO 3: SMART MONEY CONCEPT (SMC)
    if fvg and is_liq_grab:
        
        status = "EXECUTE"
        scenario = "Skenario 3: Smart Money Concept (SMC)"
        notes.append("Liquidity Grab + FVG Rejection")
        
        buffer = atr * 0.2
        sl_price = grab_level - buffer if direction == "LONG" else grab_level + buffer
        risk_dist = abs(entry_price - sl_price)
        tp_price = entry_price + (risk_dist * config.SMC_RR_RATIO) if direction == "LONG" else entry_price - (risk_dist * config.SMC_RR_RATIO)
        
        risk_calc = {
            "entry": entry_price, "stop_loss": sl_price, "take_profit": tp_price,
            "position_size": 1.0, "risk_amount": equity * config.RISK_PCT, 
            "note": f"SMC High R:R ({config.SMC_RR_RATIO}x)"
        }
        return _pack_result(status, direction, scenario, risk_calc, notes)

    # SKENARIO 5: S/D + IMBALANCE + LIQUIDITY
    if fvg and is_liq_grab: 
        
        status = "WAIT_FOR_TRIGGER" 
        scenario = "Skenario 5: S/D + Imbalance (Wait Limit)"
        notes.append("Setup Valid. Placing Virtual Limit.")
        return _pack_result(status, direction, scenario, {}, notes)

    # SKENARIO 4: MARKET SIDEWAYS (Fallback)
    if struct['snr_status'] == "STRONG" and not struct['pattern_h1']:
        pass 

    return _pack_result("WAIT", "NEUTRAL", "No Valid Scenario", {}, ["Scanning..."])

def _pack_result(status, direction, strategy, risk, notes):
    return {
        "status": status,
        "direction": direction,
        "strategy": strategy,
        "confidence": 85 if status == "EXECUTE" else 0,
        "risk": risk,
        "notes": notes,
        "fundamental": {"flag": "GREEN"} 
    }