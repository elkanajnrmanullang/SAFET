import requests
import os
from dotenv import load_dotenv

# 1. Muat Environment Variables
load_dotenv()
API_KEY = os.getenv("CRYPTOPANIC_API_KEY")

# --- KONFIGURASI ---
BASE_URL = "https://cryptopanic.com/api/v1/posts/"

def get_crypto_news(symbol, limit=5):
    """
    Mengambil berita dengan Error Handling yang kuat.
    Jika gagal, return pesan netral agar AI tetap bisa jalan.
    """
    if not API_KEY:
        return "Info: API Key Berita belum diset. Mengabaikan sentimen berita."

    # Bersihkan simbol (BTC/USDT -> BTC)
    coin_symbol = symbol.split('/')[0].upper()
    
    try:
        # TAMBAHAN PENTING: User-Agent agar tidak diblokir server
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        url = f"{BASE_URL}?auth_token={API_KEY}&currencies={coin_symbol}&filter=rising&public=true"
        
        response = requests.get(url, headers=headers, timeout=5)
        
        # Cek Status Code
        if response.status_code != 200:
            return f"Info: Gagal mengambil berita (Status {response.status_code}). Lanjut analisa teknikal."
            
        # Cek apakah response kosong sebelum parse JSON
        if not response.text.strip():
            return "Info: Server berita tidak merespon. Lanjut analisa teknikal."

        data = response.json()
        
        news_list = []
        if 'results' in data:
            for item in data['results'][:limit]:
                title = item.get('title', 'No Title')
                votes = item.get('votes', {})
                positive = votes.get('positive', 0)
                negative = votes.get('negative', 0)
                is_hot = "🔥" if (positive + negative) > 20 else ""
                
                news_list.append(f"- {is_hot} {title} (👍{positive}/👎{negative})")
        
        if not news_list:
            return "Tidak ada berita signifikan dalam 24 jam terakhir. Sentimen Netral."
            
        return "\n".join(news_list)

    except Exception as e:
        # JANGAN CRASH. Return pesan info saja.
        return f"Info: Koneksi berita skip ({str(e)}). Lanjut ke teknikal."

def analyze_sentiment_score(news_text):
    """
    Scoring sentimen. Jika berita error/kosong, anggap NEUTRAL.
    """
    # Jika input adalah pesan error/info, return NEUTRAL
    if "Info:" in news_text or "Gagal" in news_text:
        return "NEUTRAL (No Data)"

    keywords_bad = ['hack', 'sec', 'ban', 'lawsuit', 'delist', 'crash', 'dump', 'stolen', 'fraud', 'investigation']
    keywords_good = ['partnership', 'launch', 'upgrade', 'etf', 'approve', 'bull', 'ath', 'adoption', 'mainnet']
    
    score = 0
    text_lower = news_text.lower()
    
    for word in keywords_bad:
        if word in text_lower: score -= 1
        
    for word in keywords_good:
        if word in text_lower: score += 1
        
    if score > 0: return "POSITIVE"
    elif score < 0: return "NEGATIVE"
    else: return "NEUTRAL"  