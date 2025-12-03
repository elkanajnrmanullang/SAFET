import os
import mplfinance as mpf
import pandas as pd
from inference_sdk import InferenceHTTPClient
from dotenv import load_dotenv

# 1. Muat Environment Variables
load_dotenv()

API_KEY_CHART = os.getenv("ROBOFLOW_API_KEY_CHART")
API_KEY_CANDLE = os.getenv("ROBOFLOW_API_KEY_CANDLE")

MODEL_CHART_ID = "chart-pattern/2"
MODEL_CANDLE_ID = "candlestick-pattern-recognition/2"

def dataframe_to_image(df, filename="temp_vision.jpg"):
    try:
        if df is None or df.empty: return False
        # Ambil 50 candle terakhir (Zoom in untuk pola)
        subset = df.tail(50).copy()
        s = mpf.make_mpf_style(base_mpf_style='yahoo', rc={'font.size': 8})
        
        # Simpan gambar "Clean" (Candle + Volume, No Axis) sesuai Dokumen v4.1
        mpf.plot(subset, type='candle', style=s, 
                 savefig=dict(fname=filename, dpi=100),
                 axisoff=True, volume=True) # Volume diaktifkan
        return True
    except Exception as e:
        print(f"Error Gen Image: {e}")
        return False

def run_vision_inference(image_path, model_id, api_key):
    if not api_key: return [f"Error: Key {model_id} missing"]
    try:
        CLIENT = InferenceHTTPClient(
            api_url="https://detect.roboflow.com",
            api_key=api_key
        )
        result = CLIENT.infer(image_path, model_id=model_id)
        patterns = []
        if 'predictions' in result:
            for pred in result['predictions']:
                if pred['confidence'] > 0.40: 
                    patterns.append(f"{pred['class']} ({int(pred['confidence']*100)}%)")
        return patterns if patterns else ["Tidak terdeteksi"]
    except Exception as e:
        return [f"Info AI: Skip ({str(e)})"]

def detect_all_patterns(df):
    """Fungsi Utama Vision"""
    image_path = "temp_vision.jpg"
    if not dataframe_to_image(df, image_path): return "Gagal", "Gagal"

    # Hybrid Scan
    res_chart = run_vision_inference(image_path, MODEL_CHART_ID, API_KEY_CHART)
    res_candle = run_vision_inference(image_path, MODEL_CANDLE_ID, API_KEY_CANDLE)

    if os.path.exists(image_path): os.remove(image_path)
    
    return ", ".join(res_chart), ", ".join(res_candle)