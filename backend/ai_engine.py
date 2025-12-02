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
        # UPGRADE KE GEMINI 1.5 PRO (BEST REASONING)
        # Model ini lebih lambat sedikit, tapi jauh lebih pintar dan teliti.
        model = genai.GenerativeModel('gemini-1.5-pro')
        
        # Setting safety settings agar tidak memblokir analisa keuangan
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        
        response = model.generate_content(prompt_text, safety_settings=safety_settings)
        return response.text
    except Exception as e:
        return f"⚠️ Terjadi Kesalahan pada AI: {str(e)}"

# Test fungsi jika file ini dijalankan langsung
if __name__ == "__main__":
    print("🤖 Sedang mengetes koneksi ke Gemini 1.5 Pro...")
    hasil = get_gemini_analysis("Halo Gemini! Jawab singkat: Siap menganalisa market?")
    print("Jawab Gemini:")
    print(hasil)