import traceback

# CORE CONFIG & UTILS
from backend.core.config import config
from backend.core.json_unifier import json_unifier
from backend.core.performance import perf_monitor

# MODULES INTEGRATION
from backend.crypto.data import build_ai_context
from backend.crypto.engine import final_decision
from backend.vision.pattern_rec import vision_engine
from backend.analytics.explainability import ExplainabilityEngine

class AIPipeline:

    def __init__(self):
        self.version = "AI-Pipeline-7.1-Waterfall"
        self.explainer = ExplainabilityEngine()

    # MAIN PIPELINE CALL
    def run(
        self,
        symbol: str,
        user_text_context: str | None = None,
        user_image_bytes: bytes | None = None
    ) -> dict:

        # Start Performance Timer
        perf_token = perf_monitor.start()

        try:
            # VISION AI ANALYSIS (PRE-PROCESS)
            vision_result = None
            detected_pattern_name = None

            if user_image_bytes:
                vision_result = vision_engine.analyze_chart_image(user_image_bytes)
                
                if vision_result.get("pattern") and vision_result.get("pattern") != "None":
                    detected_pattern_name = vision_result.get("pattern")

            # 1. LOAD CORE CONTEXT & MARKET DATA
            ctx = build_ai_context(symbol, user_chart_context=detected_pattern_name)

            if ctx is None:
                perf_monitor.stop(perf_token, "fail")
                return json_unifier.unify({
                    "status": "error",
                    "message": "Context failed (market data empty or connection error)"
                })

            # Inject metadata tambahan ke context
            ctx["config_version"] = config.VERSION
            ctx["vision_analysis"] = vision_result

            # 2. RUN DECISION ENGINE 
            decision = final_decision(
                technical_data=ctx,
                fundamental_signals=[], 
                equity=1000,            
                atr=ctx.get("atr", 0),
                entry_price=ctx.get("price", 0)
            )

            ctx["ai_decision"] = decision
            ctx["technical_signal"] = ctx.get("trend_h4") 

            ctx["risk"] = decision.get("risk")
            
            if decision["status"] == "NO_TRADE":
                ctx["explain"] = self.explainer.explain(ctx)
                perf_monitor.stop(perf_token, "success")
                return json_unifier.unify(ctx)

            # 3. EXPLAINABILITY (NARRATIVE GENERATION)
            ctx["explain"] = self.explainer.explain(ctx)

            # 4. HEDGE / PROTECTION (OPTIONAL LAYER)
            hedge_info = {
                "active": False,
                "action": "NONE",
                "volatility_status": "NORMAL"
            }
            # Cek sederhana volatilitas dari ATR
            if ctx.get("atr", 0) > 0 and ctx.get("price", 0) > 0:
                atr_pct = (ctx["atr"] / ctx["price"]) * 100
                if atr_pct > config.EXTREME_VOL_THRESHOLD_HIGH:
                     hedge_info = {"active": True, "action": "REDUCE_SIZE", "volatility_status": "EXTREME"}
            
            ctx["hedge"] = hedge_info

            # 5. FINALIZE & UNIFY
            perf_monitor.stop(perf_token, "success")
            return json_unifier.unify(ctx)

        except Exception as e:
            perf_monitor.stop(perf_token, "fail")
            return json_unifier.unify({
                "status": "exception",
                "error": str(e),
                "trace": traceback.format_exc()
            })


pipeline = AIPipeline()