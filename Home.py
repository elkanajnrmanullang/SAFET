import streamlit as st

st.set_page_config(page_title="Alta Group DSS", layout="wide", page_icon="🏰")

st.title("🏰 Altavara Group Decision System")
st.markdown("---")
st.write("### Selamat datang, Sir.")
st.write("Sistem siap membantu keputusan investasi Anda.")

col1, col2 = st.columns(2)
with col1:
    st.info("**AltaQuant (Crypto)**\nFokus: Analisa Whitepaper & Teknikal")
with col2:
    st.info("**AltaFX (Forex)**\nFokus: Makro Ekonomi & Sentimen")

st.success("Status Sistem: 🟢 Online")
