import os

# Struktur yang akan dibangun
folders = [
    "backend",
    "pages",
    "data",
    "assets"
]

files = {
    "Home.py": """import streamlit as st

st.set_page_config(page_title="Alta Group DSS", layout="wide", page_icon="🏰")

st.title("🏰 Altavara Group Decision System")
st.markdown("---")
st.write("### Selamat datang, Sir.")
st.write("Sistem siap membantu keputusan investasi Anda.")

col1, col2 = st.columns(2)
with col1:
    st.info("**AltaQuant (Crypto)**\\nFokus: Analisa Whitepaper & Teknikal")
with col2:
    st.info("**AltaFX (Forex)**\\nFokus: Makro Ekonomi & Sentimen")

st.success("Status Sistem: 🟢 Online")
""",
    ".env": "GEMINI_API_KEY=MASUKKAN_KEY_DISINI",
    "backend/__init__.py": "",
    "backend/ai_engine.py": "# Logika koneksi ke Google Gemini",
    "backend/crypto_data.py": "# Logika tarik data CCXT",
    "backend/forex_data.py": "# Logika tarik data Forex",
    "backend/database.py": "# Logika database SQLite",
    "pages/1_🚀_AltaQuant_Crypto.py": "import streamlit as st\nst.title('AltaQuant - Crypto Analyst')",
    "pages/2_💱_AltaFX_Forex.py": "import streamlit as st\nst.title('AltaFX - Forex Engine')"
}

def build_structure():
    base = os.getcwd()
    print(f"🛠️ Membangun sistem di: {base}")

    # Buat Folder
    for folder in folders:
        path = os.path.join(base, folder)
        os.makedirs(path, exist_ok=True)
        print(f"Folder Created: {folder}")

    # Buat File
    for filename, content in files.items():
        path = os.path.join(base, filename)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"File Created: {filename}")
        else:
            print(f"File Exists: {filename}")

    print("\nSetup Selesai! Silakan jalankan 'streamlit run Home.py'")

if __name__ == "__main__":
    build_structure()