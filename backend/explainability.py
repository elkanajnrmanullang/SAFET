"""
AI Explainability Layer
- Menjelaskan keputusan AI dalam bahasa manusia
- Kombinasi: rule-based + LLM narrative
- Support: GPT-OSS-120B via Groq | Gemini Flash 2.0
"""

import os
import json
import traceback
from typing import Dict, Any

import requests


class ExplainabilityEngine:

    def __init__(self):
        # Groq (GPT-OSS-120B)
        self.openai_api = os.getenv("OPENAI_BASE_URL", "")
        self.openai_key = os.getenv("OPENAI_API_KEY", "")
        self.openai_model = os.getenv("OPENAI_MODEL_NAME", "openai/gpt-oss-120b")

        # Gemini Flash 2.0
        self.gemini_key = os.getenv("GEMINI_API_KEY", "")

    # ==========================
    # LLM CALLERS
    # ==========================
    def _call_gpt_oss(self, prompt: str) -> str:
        try:
            url = f"{self.openai_api}/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.openai_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.openai_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 600
            }

            res = requests.post(url, headers=headers, data=json.dumps(payload))
            if res.status_code == 200:
                return res.json()["choices"][0]["message"]["content"]

        except Exception:
            return None

        return None

    def _call_gemini(self, prompt: str) -> str:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_key}"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            res = requests.post(url, json=payload)
            if res.status_code == 200:
                return res.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            return None

        return None

    # ==========================
    # MAIN EXPLAINABILITY
    # ==========================
    def explain(self, context: Dict[str, Any]) -> str:
        """
        context = {
           "pattern": {...},
           "anomaly": {...},
           "forecast": {...},
           "risk": {...}
        }
        """

        prompt = f"""
        Jelaskan analisa trading berdasarkan data berikut:

        {json.dumps(context, indent=2)}

        Format yang dibutuhkan:
        1. Ringkasan Perilaku Market
        2. Pola Teknis yang Terdeteksi
        3. Deteksi Anomali (pump/dump/volume)
        4. Probabilitas arah market
        5. Risiko & proteksi yang direkomendasikan
        6. Kesimpulan (1 paragraf)

        Buat dalam bahasa profesional, jelas, dan actionable.
        """

        # Try GPT-OSS-120B first
        out = self._call_gpt_oss(prompt)
        if out:
            return out

        # Try Gemini if GPT-OSS timeout
        out = self._call_gemini(prompt)
        if out:
            return out

        # Final fallback = rule-based text (simple)
        return self._fallback_explanation(context)

    # ==========================
    # FALLBACK
    # ==========================
    def _fallback_explanation(self, ctx: Dict[str, Any]) -> str:
        anomaly = ctx.get("anomaly", {})
        forecast = ctx.get("forecast", {})
        risk = ctx.get("risk", {})

        txt = "Market Summary:\n"

        if anomaly.get("anomaly"):
            txt += f"- Anomali terdeteksi: {anomaly.get('reasons', 'unknown')}\n"
        else:
            txt += "- Tidak ada anomali signifikan.\n"

        txt += f"- Probabilitas Bullish: {forecast.get('bullish_prob', 0):.2f}\n"
        txt += f"- Probabilitas Bearish: {forecast.get('bearish_prob', 0):.2f}\n"
        txt += f"- Saran Risk: {risk.get('suggestion', 'N/A')}\n"

        return txt


if __name__ == "__main__":
    e = ExplainabilityEngine()
    print(e.explain({
        "pattern": {"detected": "Bullish Flag"},
        "anomaly": {"anomaly": False},
        "forecast": {"bullish_prob": 0.62, "bearish_prob": 0.38},
        "risk": {"suggestion": "SL di 0.8%, TP di 1.5%"}
    }))
