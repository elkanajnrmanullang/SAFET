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
                "pipeline_version": ctx.get("pipeline_version", "AI-Pipeline-7.1")
            },

            "market": {
                "symbol": ctx.get("symbol"),
                "price": ctx.get("price"),
                # Pastikan ini mengambil data yang benar dari context
                "trend_4h": ctx.get("trend_h4", {}).get("direction", "NEUTRAL"),
                "atr": ctx.get("atr")
            },

            # BAGIAN PENTING: Mengirim hasil Vision AI ke UI
            "vision_analysis": ctx.get("vision_analysis"),

            # Detail Teknis untuk UI Box (H4, H1)
            "technical_signal": ctx.get("technical_signal"),
            
            # Detail Struktur (M30/M15 detail ada di dalam final_decision -> notes)
            "microstructure": ctx.get("microstructure"),

            # Detail Risk (SL/TP/Size)
            "risk": ctx.get("risk", {}),

            "hedge": ctx.get("hedge"),

            # Keputusan Akhir (Status, Reason, Notes)
            "final_decision": ctx.get("ai_decision"),

            # Penjelasan Naratif
            "explainability": ctx.get("explain")
        }

json_unifier = JSONUnifier()