import os
import google.generativeai as genai
from dotenv import load_dotenv

# 1. Muat API Key
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ ERROR: API Key tidak ditemukan di file .env")
else:
    genai.configure(api_key=api_key)

def get_gemini_analysis(prompt_text):
    """
    Fungsi ini mengirim data ke Gemini dan meminta analisa.
    """
    try:
        # KITA GUNAKAN MODEL TERBARU YG TERSEDIA DI AKUN ANDA
        # Gemini 2.0 Flash sangat cepat dan efisien untuk teks panjang
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        response = model.generate_content(prompt_text)
        return response.text
    except Exception as e:
        return f"⚠️ Terjadi Kesalahan pada AI: {str(e)}"

# Test fungsi jika file ini dijalankan langsung
if __name__ == "__main__":
    print("🤖 Sedang mengetes koneksi ke Gemini 2.0...")
    
    # Coba kirim pesan
    hasil = get_gemini_analysis("Halo Gemini! Jawab singkat: Siap menganalisa market?")
    print("Jawab Gemini:")
    print(hasil)