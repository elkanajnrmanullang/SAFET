"""
Main Pipeline (CORE)
--------------------
Orkestrator seluruh komponen AI Trading AltaQuant:
1. Vision AI Analysis (User Chart Context)
2. Market Data Loading (1000 Candle H4/H1)
3. Technical Waterfall Execution (H4 -> H1 -> M30 -> M15)
4. Risk & Money Management (Fixed 1:2 RR)
5. Explainability Layer (AI Narrative)
"""

import traceback

# =============================
# CORE CONFIG & UTILS
# =============================
from backend.core.config import config
from backend.core.json_unifier import json_unifier
from backend.core.performance import perf_monitor

# =============================
# MODULES INTEGRATION
# =============================
from backend.crypto.data import build_ai_context
from backend.crypto.engine import final_decision
from backend.vision.pattern_rec import vision_engine
from backend.analytics.explainability import ExplainabilityEngine

class AIPipeline:

    def __init__(self):
        self.version = "AI-Pipeline-7.1-Waterfall"
        self.explainer = ExplainabilityEngine()

    # ========================
    # MAIN PIPELINE CALL
    # ========================
    def run(
        self,
        symbol: str,
        user_text_context: str | None = None,
        user_image_bytes: bytes | None = None
    ) -> dict:
        """
        Menjalankan satu siklus analisis penuh untuk sebuah simbol.
        Mendukung input gambar untuk validasi pola chart hybrid.
        """

        # Start Performance Timer
        perf_token = perf_monitor.start()

        try:
            # ----------------------------------------------------
            # 0. VISION AI ANALYSIS (PRE-PROCESS)
            # ----------------------------------------------------
            # Jika user upload gambar, kita analisis dulu polanya
            vision_result = None
            detected_pattern_name = None

            if user_image_bytes:
                # Panggil Gemini Vision via vision_engine
                vision_result = vision_engine.analyze_chart_image(user_image_bytes)
                
                # Jika ditemukan pola valid, simpan namanya untuk konteks H4
                if vision_result.get("pattern") and vision_result.get("pattern") != "None":
                    detected_pattern_name = vision_result.get("pattern")

            # ----------------------------------------------------
            # 1. LOAD CORE CONTEXT & MARKET DATA
            # ----------------------------------------------------
            # Kita masukkan pattern dari Vision AI ke dalam build_ai_context
            # agar nanti bisa divalidasi arahnya di evaluate_technical (H4 Anchor)
            ctx = build_ai_context(symbol, user_chart_context=detected_pattern_name)

            if ctx is None:
                perf_monitor.stop(perf_token, "fail")
                return json_unifier.unify({
                    "status": "error",
                    "message": "Context failed (market data empty or connection error)"
                })

            # Inject metadata tambahan ke context
            ctx["config_version"] = config.VERSION
            ctx["vision_analysis"] = vision_result # Simpan hasil raw vision untuk UI

            # ----------------------------------------------------
            # 2. RUN DECISION ENGINE (THE WATERFALL)
            # ----------------------------------------------------
            # Engine ini yang akan menjalankan urutan:
            # H4 (Anchor) -> H1 (Bias) -> M30 (Setup) -> M15 (Exec) -> Risk
            
            decision = final_decision(
                technical_data=ctx,
                fundamental_signals=[], # Placeholder, bisa diisi dari news.py jika perlu
                equity=1000,            # Default equity simulasi
                atr=ctx.get("atr", 0),
                entry_price=ctx.get("price", 0)
            )

            # Simpan keputusan ke context utama
            ctx["ai_decision"] = decision
            ctx["technical_signal"] = ctx.get("trend_h4") # Pointer shortcut untuk unifier

            # Ambil data risk & structure yang dihasilkan engine
            ctx["risk"] = decision.get("risk")
            
            # Jika status NO_TRADE karena Technical/Context Conflict, kita stop di sini
            if decision["status"] == "NO_TRADE":
                # Generate penjelasan kenapa ditolak
                ctx["explain"] = self.explainer.explain(ctx)
                perf_monitor.stop(perf_token, "success")
                return json_unifier.unify(ctx)

            # ----------------------------------------------------
            # 3. EXPLAINABILITY (NARRATIVE GENERATION)
            # ----------------------------------------------------
            # Membuat penjelasan naratif (Why H4 valid? Why M30 passed? etc)
            ctx["explain"] = self.explainer.explain(ctx)

            # ----------------------------------------------------
            # 4. HEDGE / PROTECTION (OPTIONAL LAYER)
            # ----------------------------------------------------
            # Note: Risk Management utama (SL/TP) sudah ditangani oleh Engine
            # menggunakan Fixed 1:2 RR. Bagian ini hanya untuk flag volatility ekstrem.
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

            # ----------------------------------------------------
            # 5. FINALIZE & UNIFY
            # ----------------------------------------------------
            perf_monitor.stop(perf_token, "success")
            
            # Mengembalikan format JSON standar untuk Frontend
            return json_unifier.unify(ctx)

        except Exception as e:
            # Exception Handling & Logging
            perf_monitor.stop(perf_token, "fail")
            return json_unifier.unify({
                "status": "exception",
                "error": str(e),
                "trace": traceback.format_exc()
            })


# Instance Global
pipeline = AIPipeline()