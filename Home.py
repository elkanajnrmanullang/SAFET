import streamlit as st

st.set_page_config(
    page_title="AltaQuant Decision Engine", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS INJECTION (System Design v3.3) ---
st.markdown("""
<style>
    :root {
        --primary: #6366f1;
        --secondary: #10b981;
        --accent: #f59e0b;
        --danger: #ef4444;
        --bg-dark: #0f172a;
        --bg-card: #1e293b;
        --text-main: #f8fafc;
        --border: #334155;
    }
    
    /* Global Background Override */
    .stApp {
        background-color: var(--bg-dark);
        color: var(--text-main);
    }
    
    /* Custom Headers */
    h1, h2, h3 {
        color: var(--text-main) !important;
        font-family: 'Inter', sans-serif;
    }
    
    .brand-text {
        font-size: 3rem;
        font-weight: 800;
        letter-spacing: -1px;
        margin-bottom: 0;
    }
    .brand-accent { color: var(--primary); }
    
    .sub-text {
        color: #94a3b8;
        font-size: 1.1rem;
        margin-bottom: 30px;
    }
    
    /* Card Styles for Menu */
    .nav-card {
        background-color: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 20px;
        transition: transform 0.2s;
        height: 100%;
    }
    .nav-card:hover {
        border-color: var(--primary);
        transform: translateY(-5px);
    }
    .nav-title { font-weight: bold; font-size: 1.2rem; color: var(--primary); margin-bottom: 10px; }
    .nav-desc { font-size: 0.9rem; color: #cbd5e1; }

</style>
""", unsafe_allow_html=True)

# --- HEADER ---
col_logo, col_title = st.columns([1, 5])
with col_title:
    st.markdown('<div class="brand-text">ALTA<span class="brand-accent">QUANT</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-text">Decision Support System v3.3 • Hybrid Intelligence • Institutional Grade</div>', unsafe_allow_html=True)

st.divider()

# --- NAVIGATION CARDS ---
c1, c2 = st.columns(2)

with c1:
    st.markdown("""
    <div class="nav-card">
        <div class="nav-title">AltaQuant by Altavara</div>
        <div class="nav-desc">
            <ul>
                <li><strong>Fokus:</strong> Scalping (Futures) & Accumulation (Spot).</li>
                <li><strong>Engine:</strong> Vision AI + Math Logic + Gemini 2.0.</li>
                <li><strong>Fitur:</strong> Deteksi Chart Pattern otomatis & Filter Trend D1.</li>
            </ul>
        </div>
    </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown("""
    <div class="nav-card">
        <div class="nav-title">💱 AltaFX (Forex)</div>
        <div class="nav-desc">
            <ul>
                <li><strong>Fokus:</strong> Intraday & Swing Trade.</li>
                <li><strong>Engine:</strong> Macro Economic Analysis + Sentiment.</li>
                <li><strong>Fitur:</strong> Analisa Hawkish/Dovish Bank Sentral.</li>
            </ul>
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br><br>", unsafe_allow_html=True)
st.info("💡 **System Status:** Connected to AltaMaster Database. VPN Required for Binance & Roboflow.")