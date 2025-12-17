class AIConfig:
    VERSION = "AltaQuant-Forex-Logic-1.0"

    # Market Data
    DEFAULT_TIMEFRAME = "15m"
    TREND_TIMEFRAME = "1h" 
    MAX_CANDLE_LIMIT = 500

    # 1. SnR & Structure Scoring (Implementasi Objektif)
    SNR_STRONG_SCORE = 7        
    SNR_INTERMEDIATE_SCORE = 4  
    
    ATR_ZONE_WIDTH = 0.35       
    
    # Scoring Points
    SCORE_BOUNCE_BODY = 2
    SCORE_WICK_REJECTION = 1
    SCORE_FAKE_BREAKOUT = 1
    SCORE_BODY_BREAKOUT = -3
    SCORE_FRESHNESS = 1
    
    # 2. Candle Weakening (Body Compression)
    WEAKENING_RATIO = 0.65      
    WEAKENING_LOOKBACK = 10     

    # 3. Liquidity & SMC
    LIQUIDITY_TOLERANCE_M15 = 0.2  
    FVG_MIN_SIZE_ATR = 0.3         

    # Risk Management (Specific per Scenario)
    RISK_PCT = 0.01
    
    # Skenario 1 (Chart Pattern): SL 10 Poin 
    SCENARIO_1_SL_BUFFER = 0.0010 
    
    # Skenario 3 (SMC) & 5 (S/D+Liq): TP Fixed 4.97R
    SMC_RR_RATIO = 4.97 
    
    # Skenario 5: SL Buffer
    SCENARIO_5_SL_ATR = 0.5 

config = AIConfig()