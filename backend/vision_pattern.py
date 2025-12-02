import os
import mplfinance as mpf
import pandas as pd
from inference_sdk import InferenceHTTPClient
from dotenv import load_dotenv

# 1. Muat Environment Variables
load_dotenv()

# 2. Ambil Konfigurasi dari .env
# Mengambil key secara aman. Jika tidak ada di .env, return None.
API_KEY_CHART = os.getenv("ROBOFLOW_API_KEY_CHART")
API_KEY_CANDLE = os.getenv("ROBOFLOW_API_KEY_CANDLE")

# Model ID (Tetap di sini karena bukan rahasia)
MODEL_CHART_ID = "chart-pattern/2"
MODEL_CANDLE_ID = "candlestick-pattern-recognition/2"

def dataframe_to_image(df, filename="temp_vision.jpg"):
    """
    Mengubah 50 candle terakhir menjadi gambar JPG polos.
    """
    try:
        if df is None or df.empty: return False
        
        # Ambil 50 candle terakhir (Fokus pola jangka pendek)
        subset = df.tail(50).copy()
        
        # Style 'yahoo' paling bersih untuk dibaca AI
        s = mpf.make_mpf_style(base_mpf_style='yahoo', rc={'font.size': 8})
        
        # Simpan gambar TANPA sumbu harga/waktu (agar AI fokus ke bentuk)
        mpf.plot(subset, type='candle', style=s, 
                 savefig=dict(fname=filename, dpi=100),
                 axisoff=True, volume=False)
        return True
    except Exception as e:
        print(f"Error membuat gambar: {e}")
        return False

def run_vision_inference(image_path, model_id, api_key):
    """
    Fungsi generik untuk mengirim gambar ke Roboflow.
    Menerima API Key berbeda untuk setiap model.
    """
    # Safety Check: Pastikan API Key tersedia
    if not api_key:
        return [f"Error: API Key untuk {model_id} belum diset di .env"]

    try:
        # Inisialisasi Client dengan Key spesifik dari parameter
        CLIENT = InferenceHTTPClient(
            api_url="https://detect.roboflow.com",
            api_key=api_key
        )
        
        # Kirim ke Roboflow
        result = CLIENT.infer(image_path, model_id=model_id)
        
        # Parsing Hasil
        patterns = []
        if 'predictions' in result:
            for pred in result['predictions']:
                # Filter keyakinan > 40% agar tidak terlalu sensitif (false positive)
                if pred['confidence'] > 0.40: 
                    label = pred['class']
                    conf = int(pred['confidence'] * 100)
                    patterns.append(f"{label} ({conf}%)")
        
        return patterns if patterns else ["Tidak terdeteksi pola signifikan"]
        
    except Exception as e:
        return [f"Info AI: Gagal koneksi ke model {model_id} ({str(e)})"]

def detect_all_patterns(df):
    """
    FUNGSI UTAMA: 
    Menjalankan 2 Model Vision sekaligus (Chart & Candle) dan mengembalikan hasilnya.
    Dipanggil oleh backend/crypto_data.py
    """
    image_path = "temp_vision.jpg"
    
    # 1. Generate Gambar (Cukup 1x untuk kedua model)
    success = dataframe_to_image(df, image_path)
    if not success: return "Gagal Generate Image", "Gagal Generate Image"

    # 2. Cek Model 1: Candlestick Pattern (Micro)
    # Menggunakan Key Candle dari .env
    res_candle = run_vision_inference(image_path, MODEL_CANDLE_ID, API_KEY_CANDLE)
    
    # 3. Cek Model 2: Chart Pattern (Macro)
    # Menggunakan Key Chart dari .env
    res_chart = run_vision_inference(image_path, MODEL_CHART_ID, API_KEY_CHART)

    # 4. Bersihkan file temp (Kebersihan sebagian dari iman coding)
    if os.path.exists(image_path):
        os.remove(image_path)
        
    # Return 2 string hasil terpisah
    return ", ".join(res_chart), ", ".join(res_candle)