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
    Menggunakan Gemini 2.0 Flash (Terbaru & Tercepat).
    """
    try:
        # MODEL TERBARU & TERCEPAT SAAT INI
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Safety Settings (Agar tidak sensitif memblokir istilah keuangan)
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        
        response = model.generate_content(prompt_text, safety_settings=safety_settings)
        return response.text
    except Exception as e:
        # Fallback otomatis jika akun belum support 2.0, kembali ke 1.5 Flash
        if "404" in str(e) or "not found" in str(e).lower():
            print("⚠️ Gemini 2.0 belum tersedia untuk Key ini. Mengalihkan ke 1.5 Flash...")
            try:
                fallback_model = genai.GenerativeModel('gemini-1.5-flash')
                response = fallback_model.generate_content(prompt_text, safety_settings=safety_settings)
                return response.text
            except Exception as e2:
                return f"⚠️ Error Fatal AI: {str(e2)}"
        return f"⚠️ Terjadi Kesalahan pada AI: {str(e)}"

# Test fungsi jika file ini dijalankan langsung
if __name__ == "__main__":
    print("🤖 Mengetes koneksi ke Gemini 2.0 Flash (The Speed King)...")
    hasil = get_gemini_analysis("Halo Gemini! Jawab satu kata: Siap?")
    print(f"Jawab: {hasil}")