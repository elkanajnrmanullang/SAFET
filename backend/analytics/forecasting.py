import numpy as np
import pandas as pd
from openai import OpenAI
import os


class ProbForecast:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL")
        )
        self.model = os.getenv("OPENAI_MODEL_NAME")

    # =========================================================
    # 1) BAYESIAN TREND FORECAST
    # =========================================================
    def bayesian_forecast(self, df: pd.DataFrame) -> float:
        df["ret"] = df["close"].pct_change()
        up_prob = (df["ret"] > 0).sum() / len(df["ret"])
        return round(up_prob, 3)

    # =========================================================
    # 2) LLM REASONING FORECAST
    # =========================================================
    def llm_forecast(self, df: pd.DataFrame) -> float:
        data = df.tail(80).to_dict(orient="records")

        prompt = f"""
        Kamu adalah AI financial analyst.
        Dari data OHLCV berikut, berikan probabilitas bullish 0-1.

        Return hanya 1 angka probability.
        Data: {data}
        """

        try:
            res = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )

            raw = res.choices[0].message["content"]

            # Extract number
            num = float([s for s in raw.split() if s.replace('.', '', 1).isdigit()][0])
            return min(max(num, 0), 1)

        except:
            return 0.5

    # =========================================================
    # WRAPPER
    # =========================================================
    def run(self, df: pd.DataFrame) -> dict:
        bayes = self.bayesian_forecast(df)
        llm = self.llm_forecast(df)

        final_prob = (0.6 * llm) + (0.4 * bayes)

        return {
            "bayesian": bayes,
            "llm": llm,
            "final_probability": round(final_prob, 3)
        }
