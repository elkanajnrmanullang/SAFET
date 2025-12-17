import os
import requests
import json
import base64
import pandas as pd
import shutil
from datetime import datetime
from typing import Dict, Any, AnyStr, Optional, Tuple 

TEMP_VISION_DIR = "data/temp_vision"
os.makedirs(TEMP_VISION_DIR, exist_ok=True)

class PatternRecognition:
    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_key}"

    # 1. VISION AI 
    def analyze_chart_image(self, image_bytes: bytes) -> Dict[str, Any]:
        if not self.gemini_key:
            return {
                "pattern": None, 
                "sentiment": "NEUTRAL", 
                "confidence": 0, 
                "reason": "API Key Missing"
            }

        try:
            b64_image = base64.b64encode(image_bytes).decode('utf-8')
            prompt_text = """
            Kamu adalah Expert Technical Analyst di AltaQuant. 
            Tugasmu adalah menganalisis gambar chart crypto/forex yang diberikan user.
            
            FOKUS ANALISIS:
            1. Identifikasi CHART PATTERN dominan (contoh: Ascending Triangle, Bull Flag, Head & Shoulders, Double Bottom, dll).
            2. Tentukan IMPLIKASI arah (BULLISH atau BEARISH).
            3. Berikan confidence score (0.0 - 1.0).

            ATURAN:
            - Jika gambar tidak jelas, buram, atau bukan chart, kembalikan pattern: "None".
            - Jawab HANYA dalam format JSON valid. Jangan ada markdown lain.

            Format Output JSON:
            {
                "pattern_name": "Nama Pola",
                "sentiment": "BULLISH" atau "BEARISH",
                "confidence": 0.85
            }
            """

            payload = {
                "contents": [{
                    "parts": [
                        {"text": prompt_text},
                        {"inline_data": {
                            "mime_type": "image/jpeg",
                            "data": b64_image
                        }}
                    ]
                }]
            }

            response = requests.post(self.api_url, json=payload, timeout=15)
            
            if response.status_code == 200:
                res_json = response.json()
                
                try:
                    raw_text = res_json["candidates"][0]["content"]["parts"][0]["text"]
                    clean_text = raw_text.replace("```json", "").replace("```", "").strip()
                    data = json.loads(clean_text)
                    
                    ai_sentiment = data.get("sentiment", "NEUTRAL").upper()
                    internal_sentiment = "NEUTRAL"
                    
                    if "BULL" in ai_sentiment: 
                        internal_sentiment = "LONG"
                    elif "BEAR" in ai_sentiment: 
                        internal_sentiment = "SHORT"

                    return {
                        "pattern": data.get("pattern_name", "None"),
                        "sentiment": internal_sentiment,
                        "confidence": float(data.get("confidence", 0))
                    }
                except Exception as parse_error:
                    return {
                        "pattern": None,
                        "sentiment": "NEUTRAL",
                        "confidence": 0,
                        "reason": f"Parse Error: {str(parse_error)}"
                    }
            else:
                return {
                    "pattern": None, 
                    "sentiment": "NEUTRAL", 
                    "confidence": 0, 
                    "reason": f"API Error {response.status_code}"
                }

        except Exception as e:
            return {
                "pattern": None, 
                "sentiment": "NEUTRAL", 
                "confidence": 0, 
                "reason": f"Connection Error: {str(e)}"
            }

    # 2. LOCAL RULE-BASED CANDLE DETECTION (FALLBACK)
    def detect_basic_candles(self, df: pd.DataFrame) -> Dict:
        if df is None or len(df) < 3:
            return {"pattern": None, "score": 0}

        last = df.iloc[-1]
        body = abs(last["close"] - last["open"])
        
        # Menghitung sumbu 
        wick_upper = last["high"] - max(last["close"], last["open"])
        wick_lower = min(last["close"], last["open"]) - last["low"]
        total_range = last["high"] - last["low"]

        if total_range == 0: return {"pattern": None, "score": 0}

        # Hammer / Pinbar Bullish
        if wick_lower > (body * 2) and wick_upper < body:
            return {"pattern": "Hammer (Pinbar)", "score": 0.65}

        # Shooting Star / Pinbar Bearish 
        if wick_upper > (body * 2) and wick_lower < body:
            return {"pattern": "Shooting Star", "score": 0.65}

        # Marubozu 
        if body > (total_range * 0.7):
            if last["close"] > last["open"]:
                return {"pattern": "Bullish Marubozu", "score": 0.75}
            else:
                return {"pattern": "Bearish Marubozu", "score": 0.75}

        return {"pattern": None, "score": 0}

    # MAIN WRAPPER (KOMPATIBILITAS)
    def run(self, df: pd.DataFrame = None, image_bytes: bytes = None) -> Dict:
        result = {
            "vision_pattern": None,
            "basic_candle": None
        }

        if image_bytes:
            result["vision_pattern"] = self.analyze_chart_image(image_bytes)
        if df is not None and not df.empty:
            result["basic_candle"] = self.detect_basic_candles(df)

        return result
    
vision_engine = PatternRecognition()

def _safe_save_image(src_path: str) -> Optional[str]:
    try:
        if not src_path:
            return None
        if not os.path.exists(src_path):
            return None

        base_name = os.path.basename(src_path)
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        dest_name = f"{timestamp}_{base_name}"
        dest_path = os.path.join(TEMP_VISION_DIR, dest_name)
        shutil.copyfile(src_path, dest_path)
        return dest_path
    except Exception:
        return None


def accept_user_pattern(pattern_name: Optional[str], image_path: Optional[str] = None) -> dict:
    saved_path = _safe_save_image(image_path) if image_path else None

    chart_pattern = pattern_name.strip() if isinstance(pattern_name, str) and pattern_name.strip() else None
    candle_pattern = None

    return {
        "chart_pattern": chart_pattern,
        "candle_pattern": candle_pattern,
        "image_path": saved_path,
        "source": "user",
        "note": "User-provided pattern; automatic detection disabled."
    }


def detect_all_patterns(df, user_pattern_name: Optional[str] = None, user_image_path: Optional[str] = None) -> Tuple[str, str]:
    try:
        if user_pattern_name and isinstance(user_pattern_name, str) and user_pattern_name.strip():
            name = user_pattern_name.strip()
            chart_label = f"User: {name}"
            candle_label = f"User: {name} (not specified)"

            if user_image_path:
                saved = _safe_save_image(user_image_path)
                if saved:
                    chart_label += " [image_saved]"
            return chart_label, candle_label

        return "Not provided", "Not provided"
    except Exception:
        return "Not provided", "Not provided"


def clear_temp_image(path: str) -> bool:
    try:
        if not path:
            return False
        if os.path.exists(path):
            os.remove(path)
            return True
        return False
    except Exception:
        return False


if __name__ == "__main__":
    demo = accept_user_pattern("Ascending Triangle", None)
    print("Demo accept_user_pattern:", demo)
    print("Demo detect_all_patterns (with name):", detect_all_patterns(None, user_pattern_name="Head and Shoulders"))
    print("Demo detect_all_patterns (none):", detect_all_patterns(None))