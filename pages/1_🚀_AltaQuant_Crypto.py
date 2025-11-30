import streamlit as st
import plotly.graph_objects as go
from backend.crypto_data import get_mtf_analysis
from backend.ai_engine import get_gemini_analysis

st.set_page_config(page_title="AltaQuant Crypto", layout="wide")

# CSS Custom agar mirip desain HTML Anda
st.markdown("""
<style>
    .metric-card {
        background-color: #1e293b;
        border: 1px solid #334155;
        padding: 20px;
        border-radius: 10px;
        color: white;
    }
    .verdict-box {
        margin-top: 20px;
        padding: 20px;
        border-left: 5px solid #6366f1;
        background-color: #0f172a;
        font-style: italic;
    }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.header("🎮 AltaQuant Controls")
    symbol = st.text_input("Symbol", "BTC/USDT").upper()
    timeframe = st.selectbox("Timeframe", ["15m", "1h", "4h", "1d"], index=1)
    mode = st.radio("Mode", ["Spot (Investasi)", "Futures (Trading)"])
    if st.button("🚀 SCAN MARKET", type="primary"):
        st.session_state['scan'] = True

# --- MAIN LOGIC ---
if st.session_state.get('scan'):
    # 1. Tarik Data MTF
    df, data_text = get_mtf_analysis(symbol, timeframe)
    
    if df is not None:
        # Header Harga
        last_price = df['close'].iloc[-1]
        prev_price = df['close'].iloc[-2]
        change = ((last_price - prev_price) / prev_price) * 100
        color_change = "green" if change >= 0 else "red"
        
        st.markdown(f"## {symbol} <span style='color:{color_change}; font-size:0.6em'>({change:+.2f}%)</span>", unsafe_allow_html=True)

        # 2. Grafik
        fig = go.Figure(data=[go.Candlestick(x=df['timestamp'], open=df['open'], high=df['high'], low=df['low'], close=df['close'])])
        fig.update_layout(height=400, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, use_container_width=True)

        # 3. AI PROCESSING
        with st.spinner("🤖 Menggabungkan Data Teknikal & Pengetahuan Fundamental..."):
            
            # Prompt canggih dengan Format Pemisah "|||"
            prompt = f"""
            Anda adalah AltaQuant. Tugas Anda menganalisa koin {symbol}.
            Mode: {mode}.
            
            DATA PASAR (Real-time):
            {data_text}
            
            PENGETAHUAN FUNDAMENTAL (Gunakan knowledge base Anda):
            - Apa utilitas koin {symbol}?
            - Apa narasi/sektor utamanya (e.g. L1, AI, Meme, DeFi)?
            
            INSTRUKSI OUTPUT:
            Berikan output dalam 3 bagian yang dipisahkan oleh tanda "|||".
            Jangan gunakan markdown heading (#) di dalam bagian, cukup poin-poin.
            
            Bagian 1: FUNDAMENTAL & NARASI
            Jelaskan singkat utilitas koin ini dan apakah fundamentalnya kuat untuk jangka panjang.
            
            |||
            
            Bagian 2: ANALISA TEKNIKAL (MTF)
            Analisa korelasi antara Timeframe Utama dan Timeframe Besar.
            Jelaskan konfirmasi indikator (RSI, EMA, MACD).
            
            |||
            
            Bagian 3: KEPUTUSAN FINAL (Singkat & Padat)
            Format: [ACTION] - [ALASAN UTAMA]
            Action bisa: STRONG BUY / BUY / WAIT / SELL / STRONG SELL.
            Berikan area Entry jika memungkinkan.
            """
            
            response = get_gemini_analysis(prompt)
            
            # Memecah jawaban menjadi 3 bagian
            try:
                parts = response.split("|||")
                fundametal_txt = parts[0].strip()
                technical_txt = parts[1].strip()
                verdict_txt = parts[2].strip()
            except:
                # Fallback jika AI lupa format
                fundametal_txt = "Gagal memformat fundamental."
                technical_txt = response
                verdict_txt = "Lihat analisa di atas."

        # 4. TAMPILAN GRID (Sesuai Desain HTML)
        col1, col2 = st.columns(2)
        
        with col1:
            st.info("📘 **Analisa Fundamental (AI Knowledge)**")
            st.write(fundametal_txt)
            
        with col2:
            st.warning("📊 **Analisa Teknikal (Multi-Timeframe)**")
            st.write(technical_txt)
            
        # 5. VERDICT BOX (Keputusan)
        st.markdown(f"""
        <div class="verdict-box">
            <h3 style="margin:0; color: #6366f1;">🤖 ALTAQUANT VERDICT</h3>
            <p style="font-size: 1.1em; font-weight: bold;">{verdict_txt}</p>
        </div>
        """, unsafe_allow_html=True)
        
    else:
        st.error("Gagal mengambil data. Cek simbol koin.")
else:
    st.info("👈 Siap untuk misi. Masukkan parameter di kiri.")