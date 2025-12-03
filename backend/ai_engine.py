import os
import google.generativeai as genai
from openai import OpenAI
from dotenv import load_dotenv
import json
import re

# 1. Load Environment
load_dotenv()
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
CUSTOM_API_KEY = os.getenv("OPENAI_API_KEY") 
CUSTOM_BASE_URL = os.getenv("OPENAI_BASE_URL") 
CUSTOM_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "openai/gpt-oss-120b")

# 2. Setup Clients
if GEMINI_KEY:
    try:
        genai.configure(api_key=GEMINI_KEY)
    except: pass

if CUSTOM_API_KEY and CUSTOM_BASE_URL:
    openai_client = OpenAI(base_url=CUSTOM_BASE_URL, api_key=CUSTOM_API_KEY)
else:
    openai_client = None

# --- HELPER: ROBUST JSON EXTRACTOR (PENTING!) ---
def extract_json_via_regex(text):
    """
    Memaksa ambil teks hanya di antara kurung kurawal pertama { dan terakhir }
    Ini mencegah error parsing jika AI menambahkan teks pembuka/penutup.
    """
    try:
        # Cari pola JSON object {...} secara greedy (termasuk nested)
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return match.group(0)
        return text
    except:
        return text

# --- LAYER 1: GEMINI 2.0 FLASH ---
def layer1_sentiment_analysis(raw_text_data):
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        prompt = f"Analisa sentimen pasar singkat (Bullish/Bearish/Netral) dari data ini: {raw_text_data[:5000]}"
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return "Netral (Data Error)"

# --- LAYER 2: SCREENER (GPT-OSS Low Reasoning) ---
def layer2_technical_screen(symbol, price, ema200, volume_status):
    if not openai_client: return "PASS"
    
    prompt = f"SCREENING {symbol}: Price {price}, EMA200 {ema200}. PASS jika trend jelas, REJECT jika sideways parah."
    
    try:
        response = openai_client.chat.completions.create(
            model=CUSTOM_MODEL_NAME, 
            messages=[{"role": "user", "content": prompt}], 
            temperature=0.0
        )
        return response.choices[0].message.content.strip().upper()
    except: return "PASS"

# --- LAYER 3: AUDITOR (GPT-OSS High Reasoning) ---
def layer3_final_decision(symbol, context_data, sentiment_data, mode="Futures"):
    if not openai_client: return "{}"

    # PROMPT SANGAT SPESIFIK ALTAQUANT v2.2
    system_instruction = """
    [Reasoning: High]
    Anda adalah AltaQuant v2.2 (Cynical Auditor).
    
    LOGIKA AUDIT (SCIENCE-BASED & FLEXIBLE):
    1. TREND FILTER: Harga di atas EMA 200 = HANYA LONG. Di bawah = HANYA SHORT.
    
    2. VALUE ZONE (CRITICAL UPDATE): 
       - "Pullback" TIDAK HARUS terjadi pada candle terakhir.
       - Cek 10 CANDLE TERAKHIR: Apakah ada ekor/body yang menyentuh atau masuk area toleransi EMA 50?
       - Area Toleransi: Jarak harga < 1.1% dari garis EMA 50.
       - Jika sentuhan terjadi dalam 10 candle terakhir dan sekarang harga mulai memantul (rejection), ini VALID.
       - REJECT jika harga benar-benar melayang jauh (Over-extended) tanpa menyentuh zona dalam waktu lama.
       
    3. VALIDASI: Volume harus Spike saat Rejection candle terbentuk.
    4. MOMENTUM: RSI tidak boleh Divergence berlawanan.
    5. RISIKO: Stop Loss wajib menggunakan buffer ATR.

    CRITICAL: OUTPUT MUST BE RAW JSON ONLY. NO MARKDOWN. NO EXPLANATION TEXT.
    Start with { and end with }.
    """

    user_prompt = f"""
    ASET: {symbol} ({mode})
    SENTIMEN: {sentiment_data}
    DATA TEKNIS:
    {context_data}
    
    Instruksi JSON Output:
    {{
        "fundamental": "Ringkasan sentimen 1 kalimat",
        "tek_indikator": "Analisa EMA 200, EMA 50, RSI",
        "tek_candle": "Analisa Candle & Volume",
        "tek_chart": "Analisa Pola Chart",
        "support_terdekat": "Angka Harga Support",
        "resistance_terdekat": "Angka Harga Resistance",
        "summary": "Kesimpulan audit (tegas)",
        "keputusan": "LONG/SHORT/WAIT",
        "entry": "Area Entry (Dekat EMA 50)",
        "sl": "Area SL (Basis ATR)",
        "tp1": "Target 1 (R:R 1:1.5)",
        "tp2": "Target 2 (R:R 1:3)"
    }}
    """

    try:
        response = openai_client.chat.completions.create(
            model=CUSTOM_MODEL_NAME,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,
            max_tokens=1500
        )
        
        raw_content = response.choices[0].message.content
        
        # PEMBERSIHAN EKSTRA (REGEX)
        # Langkah ini krusial untuk model OSS yang sering 'banyak bicara'
        cleaned_json = extract_json_via_regex(raw_content)
        
        # Hapus markdown sisa jika masih ada
        cleaned_json = cleaned_json.replace("```json", "").replace("```", "").strip()
        
        return cleaned_json
        
    except Exception as e:
        # Return JSON error standar agar UI tidak crash
        return json.dumps({
            "summary": f"System Error: {str(e)}", 
            "keputusan": "WAIT",
            "fundamental": "-", "tek_indikator": "-", "tek_candle": "-", "tek_chart": "-",
            "support_terdekat": "-", "resistance_terdekat": "-",
            "entry": "-", "sl": "-", "tp1": "-", "tp2": "-"
        })