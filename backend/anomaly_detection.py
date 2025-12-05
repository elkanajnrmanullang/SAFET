"""
backend/anomaly_detection.py
Robust anomaly detection for crypto/forex/indices.
Outputs:
{
  "anomaly": bool,
  "severity": float 0..1,
  "reasons": [...],
  "metrics": {
      vol_z, ret_z, wick_top_ratio, wick_bottom_ratio,
      vol_score, ret_score, wick_score,
      severity_raw, threshold_alert, threshold_block
  }
}
"""

import numpy as np
import pandas as pd
from typing import Dict, Any


def _zscore(series: pd.Series, window: int = 20) -> pd.Series:
    roll_mean = series.rolling(window, min_periods=3).mean()
    roll_std = series.rolling(window, min_periods=3).std().replace(0, np.nan)
    z = (series - roll_mean) / roll_std
    return z.fillna(0)


def detect_anomaly(df: pd.DataFrame, sensitivity: str = "crypto") -> Dict[str, Any]:
    if df is None or df.empty or len(df) < 20:
        return {"anomaly": False, "severity": 0.0, "reasons": [], "metrics": {}}

    reasons = []
    metrics = {}

    # --- Volume spike analysis ---
    vol = df["volume"].astype(float)
    vol_z = _zscore(vol, window=20)
    last_vol_z = float(vol_z.iloc[-1])
    metrics["vol_z"] = last_vol_z

    # --- Price return anomaly ---
    returns = df["close"].pct_change().fillna(0)
    ret_z = _zscore(returns, window=20)
    last_ret_z = float(ret_z.iloc[-1])
    metrics["ret_z"] = last_ret_z

    # --- Wick abnormality ---
    last = df.iloc[-1]
    body = abs(last["close"] - last["open"])
    wick_top = last["high"] - max(last["open"], last["close"])
    wick_bottom = min(last["open"], last["close"]) - last["low"]

    wick_top_ratio = (wick_top / (body + 1e-9)) if body > 0 else float("inf")
    wick_bottom_ratio = (wick_bottom / (body + 1e-9)) if body > 0 else float("inf")

    metrics["wick_top_ratio"] = wick_top_ratio
    metrics["wick_bottom_ratio"] = wick_bottom_ratio

    # --- Scoring logic ---
    vol_score = min(max((abs(last_vol_z) - 1.5) / 3.5, 0.0), 1.0)
    ret_score = min(max((abs(last_ret_z) - 1.5) / 3.5, 0.0), 1.0)

    wick_score = 0.0
    if wick_top_ratio > 2.0 or wick_bottom_ratio > 2.0:
        wick_score = 0.6
        if wick_top_ratio > 5.0 or wick_bottom_ratio > 5.0:
            wick_score = 0.95

    # --- Sensitivity tuning ---
    if sensitivity == "crypto":
        severity = min(1.0, 0.45 * vol_score + 0.35 * ret_score + 0.2 * wick_score)
        threshold_alert = 0.25
        threshold_block = 0.95
    else:
        severity = min(1.0, 0.55 * vol_score + 0.35 * ret_score + 0.1 * wick_score)
        threshold_alert = 0.15
        threshold_block = 0.90

    metrics["vol_score"] = vol_score
    metrics["ret_score"] = ret_score
    metrics["wick_score"] = wick_score
    metrics["severity_raw"] = severity
    metrics["threshold_alert"] = threshold_alert
    metrics["threshold_block"] = threshold_block

    # Reasons
    if vol_score > 0.05:
        reasons.append(f"volume_spike_z={last_vol_z:.2f}")
    if ret_score > 0.05:
        reasons.append(f"return_outlier_z={last_ret_z:.2f}")
    if wick_score > 0:
        reasons.append(f"wick_abnormal(top={wick_top_ratio:.2f},bottom={wick_bottom_ratio:.2f})")

    return {
        "anomaly": severity >= threshold_alert,
        "severity": float(severity),
        "reasons": reasons,
        "metrics": metrics,
    }


# --- Self-test ---
if __name__ == "__main__":
    df = pd.DataFrame({
        "timestamp": pd.date_range(end=pd.Timestamp.utcnow(), periods=40, freq="T"),
        "open": [100 + i * 0.1 for i in range(40)],
        "high": [100.4 + i * 0.1 for i in range(40)],
        "low": [99.8 + i * 0.1 for i in range(40)],
        "close": [100 + i * 0.1 for i in range(40)],
        "volume": [100 + (i % 5) * 60 for i in range(40)],
    })
    print(detect_anomaly(df))
