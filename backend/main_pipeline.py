"""
Main Pipeline (CORE)
--------------------
Orkestrator seluruh komponen AI Trading:
- Market Data Loader (crypto_data / forex_data)
- Vision Pattern (user-provided pattern)
- Technical Evaluator
- Microstructure Scan (CHOCH/BOS)
- Risk Engine
- Hedge Engine
- Explainability Layer
- Reinforcement Learning Loop (post-trade update)

Pipeline ini dijalankan oleh:
    ai_engine.run_ai_pipeline()
"""

import traceback

# =============================
# NEW: Full AI Integration Layer
# =============================
from backend.ai_config import config
from backend.json_unifier import json_unifier
from backend.performance_monitor import perf_monitor

# =============================
# Existing Modules
# =============================
from backend.crypto_data import build_ai_context, evaluate_technical
from backend.vision_pattern import detect_all_patterns
from backend.mini_choch import detect_microstructure
from backend.risk_engine import compute_risk
from backend.hedge_engine import hedge_decision
from backend.explainability import build_explanation
from backend.reinforcement_loop import rl_post_trade_update



class AIPipeline:

    def __init__(self):
        self.version = "AI-Pipeline-7.0-Stable"

    # ========================
    # MAIN PIPELINE CALL
    # ========================
    def run(
        self,
        symbol: str,
        user_text_context: str | None = None,
        user_pattern_name: str | None = None,
        user_pattern_image: str | None = None
    ) -> dict:

        # Performance monitoring start
        perf_token = perf_monitor.start()

        try:
            # ----------------------------------------------------
            # 1. LOAD CORE CONTEXT (15m + Trend 4H)
            # ----------------------------------------------------
            ctx = build_ai_context(symbol, user_text_context)

            if ctx is None:
                perf_monitor.stop(perf_token, "fail")
                return json_unifier.unify({
                    "status": "error",
                    "message": "Context failed (market data empty)"
                })

            ctx["config_version"] = config.get("version")

            # ----------------------------------------------------
            # 2. VISION PATTERN (BY USER)
            # ----------------------------------------------------
            chart_pat, candle_pat = detect_all_patterns(
                df=None,
                user_pattern_name=user_pattern_name,
                user_image_path=user_pattern_image
            )

            ctx["chart_pattern"] = chart_pat
            ctx["candle_pattern"] = candle_pat

            # ----------------------------------------------------
            # 3. TECHNICAL VALIDATOR
            # ----------------------------------------------------
            tech_eval = evaluate_technical(ctx)
            ctx["technical_signal"] = tech_eval

            if not tech_eval.get("valid", False):
                ctx["ai_decision"] = {
                    "allow_trade": False,
                    "reason": "Technical invalid"
                }
                ctx["explain"] = build_explanation(ctx)

                perf_monitor.stop(perf_token, "success")
                return json_unifier.unify(ctx)

            # ----------------------------------------------------
            # 4. MICROSTRUCTURE (BOS/CHOCH)
            # ----------------------------------------------------
            micro = detect_microstructure(symbol)
            ctx["microstructure"] = micro

            direction = tech_eval["direction"]

            micro_pass = (
                (direction == "LONG" and micro["signal"] in ["BOS_UP", "CHOCH_UP"]) or
                (direction == "SHORT" and micro["signal"] in ["BOS_DOWN", "CHOCH_DOWN"])
            )

            if not micro_pass:
                ctx["ai_decision"] = {
                    "allow_trade": False,
                    "reason": "Microstructure does not support trend"
                }
                ctx["explain"] = build_explanation(ctx)

                perf_monitor.stop(perf_token, "success")
                return json_unifier.unify(ctx)

            # ----------------------------------------------------
            # 5. RISK ENGINE
            # ----------------------------------------------------
            risk = compute_risk(
                price=ctx["price"],
                atr=ctx["atr"],
                direction=direction
            )
            ctx["risk"] = risk

            # ----------------------------------------------------
            # 6. HEDGE ENGINE
            # ----------------------------------------------------
            hedge = hedge_decision(
                symbol=symbol,
                direction=direction,
                risk=risk
            )
            ctx["hedge"] = hedge

            # ----------------------------------------------------
            # 7. FINAL DECISION
            # ----------------------------------------------------
            ctx["ai_decision"] = {
                "allow_trade": True,
                "direction": direction,
                "position_size": risk["position_size"],
                "stop_loss": risk["stop_loss"],
                "take_profit": risk["take_profit"],
                "hedge_action": hedge.get("hedge_action")
            }

            # ----------------------------------------------------
            # 8. EXPLAINABILITY
            # ----------------------------------------------------
            ctx["explain"] = build_explanation(ctx)

            # ----------------------------------------------------
            # 9. RL POST-UPDATE (optional)
            # ----------------------------------------------------
            try:
                rl_post_trade_update(ctx)
            except:
                pass

            # =========================================
            # FINAL: unification + performance logging
            # =========================================
            perf_monitor.stop(perf_token, "success")
            return json_unifier.unify(ctx)

        except Exception as e:

            # Exception catch logging
            perf_monitor.stop(perf_token, "fail")

            return json_unifier.unify({
                "status": "exception",
                "error": str(e),
                "trace": traceback.format_exc()
            })


# Default instance
pipeline = AIPipeline()
