import streamlit as st
import plotly.graph_objects as go
import json
import re
import time
from backend.crypto_data import get_ai_context_indo, scan_dynamic_market, get_market_overview
from backend.ai_engine import get_gemini_analysis

st.set_page_config(page_title="AltaQuant Pro", layout="wide")

# --- CSS (UI Professional) ---
st.markdown("""
<style>
    :root {--bg-card:#1e293b; --text-gray:#94a3b8; --green:#10b981; --red:#ef4444;}
    .report-grid {display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top:10px;}
    .card-box {background: var(--bg-card); padding: 15px; border-radius: 8px; border: 1px solid #334155;}
    .card-header {color: var(--text-gray); font-size: 0.8rem; text-transform: uppercase; font-weight: bold; margin-bottom: 8px;}
    .main-text {color: #f1f5f9; font-size: 0.95rem; line-height: 1.5;}
    .plan-row {display: flex; justify-content: space-between; gap: 10px;}
    .plan-item {background: #0f172a; padding: 10px; border-radius: 5px; width: 100%; text-align: center;}
    .plan-label {font-size: 0.7rem; color: #64748b; margin-bottom: 4px;}
    .plan-val {font-weight: bold; font-size: 1rem;}
    .verdict-box {margin-top: 15px; padding: 15px; border-radius: 8px; border-left: 5px solid;}
    
    /* DASHBOARD STYLES */
    .hero-metric {background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); padding: 20px; border-radius: 10px; border: 1px solid #334155; text-align: center;}
    .metric-val {font-size: 2rem; font-weight: 800; color: white;}
    .metric-lbl {font-size: 0.9rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px;}
    .intro-box {background: rgba(99, 102, 241, 0.1); border: 1px solid #6366f1; padding: 20px; border-radius: 10px; margin-bottom: 20px;}
</style>
""", unsafe_allow_html=True)

# --- FUNGSI PARSING & CHART ---
def parse_indo_json(text):
    try:
        clean = re.sub(r'```json\s*|\s*```', '', text).strip()
        return json.loads(clean)
    except:
        return {
            "fundamental": "Gagal membaca.", "teknikal": "Gagal membaca.",
            "chart_pattern": "-", "candle_pattern": "-", "keputusan": "WAIT",
            "entry": "-", "sl": "-", "tp": "-", "alasan": text[:300]
        }

def plot_tv_chart(df, symbol):
    fig = go.Figure(data=[go.Candlestick(
        x=df['timestamp'], open=df['open'], high=df['high'], low=df['low'], close=df['close'],
        increasing_line_color='#26a69a', decreasing_line_color='#ef5350'
    )])
    last = df['close'].iloc[-1]
    fig.add_hline(y=last, line_dash="dash", line_color="white", annotation_text=f" {last}")
    fig.update_layout(height=400, margin=dict(t=30, b=0, l=0, r=0), xaxis_rangeslider_visible=False, paper_bgcolor="#0f172a", plot_bgcolor="#0f172a", xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor="#1e293b"), title=dict(text=f"{symbol} (H1)", font=dict(color="white")))
    return fig

# --- RENDER KARTU ---
def render_card(sym, data, chart_fig, sys_bias):
    action = data.get('keputusan', 'WAIT').upper()
    color = "#10b981" if "LONG" in action or "BUY" in action else "#ef4444" if "SHORT" in action or "SELL" in action else "#94a3b8"
    
    st.plotly_chart(chart_fig, use_container_width=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"""
        <div class="card-box"><div class="card-header">🌍 Fundamental</div><div class="main-text">{data.get('fundamental')}</div></div>
        <div class="card-box" style="margin-top:10px;"><div class="card-header">📐 Pola</div><div class="main-text"><b>Chart:</b> {data.get('chart_pattern')}<br><b>Candle:</b> {data.get('candle_pattern')}</div></div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="card-box"><div class="card-header">📊 Teknikal</div><div class="main-text">{data.get('teknikal')}</div></div>
        <div class="card-box" style="margin-top:10px; border-color: {color};"><div class="card-header" style="color:{color};">⚡ Plan ({action})</div>
            <div class="plan-row">
                <div class="plan-item"><div class="plan-label">ENTRY</div><div class="plan-val" style="color:white;">{data.get('entry')}</div></div>
                <div class="plan-item"><div class="plan-label">SL</div><div class="plan-val" style="color:#ef4444;">{data.get('sl')}</div></div>
                <div class="plan-item"><div class="plan-label">TP</div><div class="plan-val" style="color:#10b981;">{data.get('tp')}</div></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    st.markdown(f'<div class="verdict-box" style="border-color:{color};background:{color}10;"><strong>🤖 Verdict:</strong> "{data.get('alasan')}"</div><hr style="border-color:#334155;">', unsafe_allow_html=True)

# --- MAIN APP LOGIC ---

# 1. SIDEBAR CONTROLS
with st.sidebar:
    st.header("AltaQuant V4.1")
    mode = st.radio("Mode", ["Manual Input", "Auto-Discovery (Full Market)"])
    if mode == "Manual Input":
        sym_in = st.text_input("Simbol", "BTC/USDT").upper()
        targets = [{'symbol': sym_in, 'bias': 'MANUAL'}]
    else:
        st.info("Scanner akan memfilter volume likuiditas dan mencari setup terbaik.")
        targets = []
    btn = st.button("MULAI ANALISA", type="primary")

# 2. INISIALISASI STATE (Agar UI tidak hilang saat refresh)
if 'result_data' not in st.session_state:
    st.session_state['result_data'] = None

# 3. UI LANDING PAGE (DASHBOARD AWAL)
if not st.session_state['result_data'] and not btn:
    # Header Welcome
    st.markdown("""
    <div class="intro-box">
        <h2 style="margin:0; color: #818cf8;">👋 Selamat Datang di AltaQuant Decision Engine</h2>
        <p style="margin-top:5px; color: #cbd5e1;">Sistem ini menggunakan algoritma Institutional Grade untuk memindai pasar Crypto secara real-time. Silakan pilih mode di sidebar untuk memulai.</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Live Market Ticker
    overview = get_market_overview()
    c1, c2, c3 = st.columns(3)
    with c1:
        color_btc = "#10b981" if overview['btc_change'] >= 0 else "#ef4444"
        st.markdown(f'<div class="hero-metric"><div class="metric-lbl">Bitcoin (BTC)</div><div class="metric-val" style="color:{color_btc};">${overview["btc_price"]:.2f}</div></div>', unsafe_allow_html=True)
    with c2:
        color_eth = "#10b981" if overview['eth_change'] >= 0 else "#ef4444"
        st.markdown(f'<div class="hero-metric"><div class="metric-lbl">Ethereum (ETH)</div><div class="metric-val" style="color:{color_eth};">${overview["eth_price"]:.2f}</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="hero-metric"><div class="metric-lbl">System Status</div><div class="metric-val" style="color:#6366f1;">ONLINE</div></div>', unsafe_allow_html=True)

# 4. PROSES ANALISA (LOADING BAR)
if btn:
    # Reset hasil lama
    st.session_state['result_data'] = []
    
    # A. LOADING PROGRESS
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        # Step 1: Scan Market
        if mode == "Auto-Discovery (Full Market)":
            status_text.text("🔍 [10%] Menghubungkan ke Binance Exchange...")
            progress_bar.progress(10)
            time.sleep(0.5)
            
            status_text.text("🔍 [30%] Memindai Likuiditas Volume > $30 Juta...")
            targets = scan_dynamic_market()
            progress_bar.progress(40)
            
            if not targets:
                targets = [{'symbol': 'BTC/USDT', 'bias': 'NEUTRAL'}]
        
        # Step 2: Analisa per Koin
        final_results = []
        total_targets = len(targets)
        
        for idx, t in enumerate(targets):
            sym = t['symbol']
            current_progress = 40 + int((idx / total_targets) * 50) # 40% sampai 90%
            
            status_text.text(f"🧠 [{current_progress}%] Menganalisa Fundamental & Teknikal: {sym}...")
            progress_bar.progress(current_progress)
            
            df, context = get_ai_context_indo(sym)
            
            if df is not None:
                # Prompt AI
                prompt = f"""
                Role: Senior Crypto Trader. Analyze {sym}. Bias: {t['bias']}.
                Data: {context}.
                Output JSON: fundamental, teknikal, chart_pattern, candle_pattern, keputusan (LONG/SHORT), entry, sl, tp, alasan.
                """
                raw_res = get_gemini_analysis(prompt)
                parsed_data = parse_indo_json(raw_res)
                
                # Simpan Hasil ke Memory
                final_results.append({
                    'symbol': sym, 'data': parsed_data, 'df': df, 'bias': t['bias']
                })
        
        # Step 3: Selesai
        status_text.text("✅ [100%] Menyusun Laporan Akhir...")
        progress_bar.progress(100)
        time.sleep(0.5)
        
        # Bersihkan Loading UI
        status_text.empty()
        progress_bar.empty()
        
        # Simpan ke Session State agar tampil
        st.session_state['result_data'] = final_results
        
        # Rerun agar UI Landing Page hilang dan ganti jadi hasil
        st.rerun()

    except Exception as e:
        st.error(f"Terjadi kesalahan sistem: {e}")

# 5. TAMPILKAN HASIL AKHIR
if st.session_state['result_data']:
    st.markdown("### 🚀 Hasil Analisa AltaQuant")
    for res in st.session_state['result_data']:
        chart = plot_tv_chart(res['df'], res['symbol'])
        render_card(res['symbol'], res['data'], chart, res['bias'])