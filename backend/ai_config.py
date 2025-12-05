"""
Global AI Configuration
-----------------------
Seluruh parameter inti AI Trading dipusatkan agar:
- Konsisten di seluruh modul
- Mudah dilakukan tuning oleh RL atau developer
- Bisa di-load di environment lain (prod / staging / simulation)
"""

class AIConfig:
    VERSION = "AI-Core-Config-3.0"

    # =====================================================
    # Market Data
    # =====================================================
    DEFAULT_TIMEFRAME = "15m"
    TREND_TIMEFRAME = "4h"
    MAX_CANDLE_LIMIT = 500

    # =====================================================
    # Technical Evaluator
    # =====================================================
    TREND_STRONG_THRESHOLD = 0.65  # min strength long/short

    # =====================================================
    # Microstructure (CHOCH/BOS)
    # =====================================================
    MICRO_CONFIRMATION_REQUIRED = True

    # =====================================================
    # Risk Engine
    # =====================================================
    RISK_PCT = 0.01
    ATR_MULTIPLIER_SL = 1.7
    ATR_MULTIPLIER_TP = 3.4

    # =====================================================
    # Hedge Engine
    # =====================================================
    EXTREME_VOL_THRESHOLD_LOW = 0.018
    EXTREME_VOL_THRESHOLD_HIGH = 0.030

    # =====================================================
    # RL System
    # =====================================================
    RL_ENABLED = True
    RL_LEARNING_RATE = 0.05

    # =====================================================
    # Explainability
    # =====================================================
    ENABLE_EXPLAINER = True


config = AIConfig()
