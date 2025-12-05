"""
JSON Structure Unifier
----------------------
Tujuan:
- Menyatukan format output dari seluruh modul (technical, microstructure,
  risk, hedge, vision pattern, explainability)
- Memastikan AI Engine selalu mengirim JSON final yang clean, aman,
  dan siap dikonsumsi oleh LLM / Dashboard / Execution Layer.
"""

from typing import Dict, Any


class JSONUnifier:

    @staticmethod
    def unify(ctx: Dict[str, Any]) -> Dict[str, Any]:
        """
        ctx: raw pipeline context
        output: final standardized JSON object
        """

        return {
            "meta": {
                "engine_version": ctx.get("engine_version", "Unknown"),
                "pipeline_version": ctx.get("pipeline_version", "AI-Pipeline-7.0")
            },

            "market": {
                "symbol": ctx.get("symbol"),
                "price": ctx.get("price"),
                "trend_4h": ctx.get("trend_4h"),
                "trend_15m": ctx.get("trend_15m"),
                "atr": ctx.get("atr")
            },

            "patterns": {
                "chart": ctx.get("chart_pattern"),
                "candle": ctx.get("candle_pattern")
            },

            "technical_signal": ctx.get("technical_signal"),
            "microstructure": ctx.get("microstructure"),

            "risk": {
                "position_size": ctx.get("risk", {}).get("position_size"),
                "stop_loss": ctx.get("risk", {}).get("stop_loss"),
                "take_profit": ctx.get("risk", {}).get("take_profit"),
                "atr": ctx.get("atr")
            },

            "hedge": ctx.get("hedge"),

            "final_decision": ctx.get("ai_decision"),

            "explainability": ctx.get("explain")
        }


json_unifier = JSONUnifier()
