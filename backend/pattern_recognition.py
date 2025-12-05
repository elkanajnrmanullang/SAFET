import os
import requests
import numpy as np
import pandas as pd
from openai import OpenAI
from typing import Dict


class PatternRecognition:
    def __init__(self):
        self.roboflow_chart = os.getenv("ROBOFLOW_API_KEY_CHART")
        self.roboflow_candle = os.getenv("ROBOFLOW_API_KEY_CANDLE")

        self.groq_client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL")
        )
        
        self.gemini_key = os.getenv("GEMINI_API_KEY")

    # =========================================================
    # 1) RULE-BASED CANDLE DETECTION
    # =========================================================
    def detect_basic_candles(self, df: pd.DataFrame) -> Dict:
        if len(df) < 3:
            return {"pattern": None, "score": 0}

        last = df.iloc[-1]
        body = abs(last["close"] - last["open"])
        wick_upper = last["high"] - max(last["close"], last["open"])
        wick_lower = min(last["close"], last["open"]) - last["low"]

        # Hammer
        if wick_lower > body * 2 and wick_upper < body:
            return {"pattern": "Hammer", "score": 0.65}

        # Shooting Star
        if wick_upper > body * 2 and wick_lower < body:
            return {"pattern": "Shooting Star", "score": 0.65}

        return {"pattern": None, "score": 0}

    # =========================================================
    # 2) CHART PATTERN VIA ROBOFLOW
    # =========================================================
    def detect_chart_pattern(self, image_base64: str):
        url = f"https://detect.roboflow.com/chart-pattern/1?api_key={self.roboflow_chart}"
        try:
            resp = requests.post(url, data=image_base64)
            return resp.json()
        except:
            return {"pattern": None, "confidence": 0}

    # =========================================================
    # 3) CANDLE PATTERN VIA ROBOFLOW
    # =========================================================
    def detect_candle_ai(self, image_base64: str):
        url = f"https://detect.roboflow.com/candlestick-pattern/1?api_key={self.roboflow_candle}"
        try:
            resp = requests.post(url, data=image_base64)
            return resp.json()
        except:
            return {"pattern": None, "confidence": 0}

    # =========================================================
    # 4) AI REASONING (GPT-OSS-120b / Gemini)
    # =========================================================
    def ai_reason_pattern(self, df: pd.DataFrame) -> Dict:
        ohlcv_json = df.tail(60).to_dict(orient="records")

        prompt = f"""
        Kamu adalah AI yang menganalisis pola candlestick dan chart pattern.
        Berikan 1 pola paling dominan, confidence 0-1, dan alasan singkat.

        OHLCV data (last 60 rows):
        {ohlcv_json}
        """

        try:
            res = self.groq_client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL_NAME"),
                messages=[{"role": "user", "content": prompt}]
            )
            return {"ai_pattern": res.choices[0].message["content"], "score": 0.85}

        except Exception:
            return {"ai_pattern": None, "score": 0}

    # =========================================================
    # MAIN WRAPPER
    # =========================================================
    def run(self, df: pd.DataFrame) -> Dict:
        basic = self.detect_basic_candles(df)
        ai = self.ai_reason_pattern(df)

        final = {
            "basic_pattern": basic,
            "ai_recognition": ai,
        }
        return final
