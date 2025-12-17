import os
import json
from typing import Dict, Any
import requests
from dotenv import load_dotenv  

load_dotenv()

class ExplainabilityEngine:

    def __init__(self):
        self.openai_api = os.getenv("OPENAI_BASE_URL")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.openai_model = os.getenv("OPENAI_MODEL_NAME", "openai/gpt-oss-120b")
        self.gemini_key = os.getenv("GEMINI_API_KEY")

    # LLM CALLERS
    def _call_gpt_oss(self, prompt: str) -> str:
        if not self.openai_api or not self.openai_key:
            print("Explainability: OPENAI_BASE_URL atau OPENAI_API_KEY belum diset.")
            return None

        try:
            base_url = self.openai_api.rstrip('/')
            url = f"{base_url}/chat/completions"
            
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

            res = requests.post(url, headers=headers, data=json.dumps(payload), timeout=15)
            if res.status_code == 200:
                return res.json()["choices"][0]["message"]["content"]
            else:
                print(f"GPT-OSS Error {res.status_code}: {res.text}")
                return None

        except Exception as e:
            print(f"GPT-OSS Exception: {str(e)}")
            return None

    def _call_gemini(self, prompt: str) -> str:
        if not self.gemini_key:
            print("Explainability: GEMINI_API_KEY belum diset.")
            return None

        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_key}"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            
            res = requests.post(url, json=payload, timeout=15)
            if res.status_code == 200:
                data = res.json()
                if "candidates" in data and len(data["candidates"]) > 0:
                    return data["candidates"][0]["content"]["parts"][0]["text"]
            
            print(f"Gemini Error {res.status_code}: {res.text}")
            return None
            
        except Exception as e:
            print(f"Gemini Exception: {str(e)}")
            return None

    # MAIN EXPLAINABILITY
    def explain(self, context: Dict[str, Any]) -> str:
        try:
            context_str = json.dumps(context, indent=2, default=str)
        except:
            context_str = str(context)

        # --- PROMPT SUMMARY ---
        prompt = f"""
        Anda adalah Senior Crypto Analyst di AltaQuant. 
        Tugas Anda adalah memberikan "Executive Summary" berdasarkan data independen berikut.
        Jangan jelaskan langkah per langkah seperti robot, tapi rangkum *kualitas setup* ini.

        DATA PASAR:
        {context_str}

        INSTRUKSI OUTPUT:
        1. **Kondisi Makro (H4/H1)**: Apakah tren mendukung?
        2. **Kondisi Mikro (M30/M15)**: Apakah ada setup valid atau kita masih menunggu? (Jelaskan spesifik: trigger apa yang ditunggu?)
        3. **Faktor Risiko**: Sebutkan jika ada hal yang menghalangi trade (Blockers).
        4. **Rekomendasi Akhir**: (EXECUTE / WATCHLIST / IGNORE). Berikan alasan singkat.

        Gunakan bahasa Indonesia yang profesional, padat, dan langsung pada inti.
        """

        # 1. Primary LLM (GPT-OSS / Groq)
        out = self._call_gpt_oss(prompt)
        if out: return out

        # 2. Secondary LLM (Gemini)
        out = self._call_gemini(prompt)
        if out: return out

        # 3. Final fallback
        return self._fallback_explanation(context)

    # FALLBACK (RULE BASED)
    def _fallback_explanation(self, ctx: Dict[str, Any]) -> str:
        decision = ctx.get("ai_decision", {}) 
        
        status = decision.get("status", "UNKNOWN")
        reason = decision.get("reason", "-")
        direction = decision.get("direction", "None")
        
        return f"""
        **AI Offline Mode**
        
        Sistem memutuskan: **{status}** ({direction})
        Alasan Utama: {reason}
        
        (Penjelasan detail tidak tersedia karena koneksi ke LLM Analyst gagal. Cek terminal untuk detail error API).
        """