import streamlit as st
import plotly.graph_objects as go
import json
import re
# Import Layer Hybrid
from backend.crypto_data import get_ai_context_indo, scan_dynamic_market, get_market_overview
from backend.ai_engine import layer1_sentiment_analysis, layer2_technical_screen, layer3_final_decision
from backend.database import save_trade, get_history, update_outcome_and_learn, get_performance_stats

st.set_page_config(page_title="AltaQuant Pro", layout="wide")

# CSS Styling (Tetap sama, hanya tambah style table kecil)
st.markdown("""
<style>
    :root { --primary: #6366f1; --secondary: #10b981; --accent: #f59e0b; --danger: #ef4444; --bg-card: #1e293b; --text-main: #f8fafc; --text-muted: #94a3b8; --border: #334155; --futures-color: #f43f5e; }
    .output-container { border: 1px solid var(--border); border-radius: 12px; overflow: hidden; margin-bottom: 20px; background: var(--bg-card); }
    .card-header { padding: 15px 25px; display: flex; justify-content: space-between; border-bottom: 1px solid; }
    .futures-header { background: linear-gradient(90deg, rgba(244, 63, 94, 0.2), transparent); border-bottom-color: var(--futures-color); }
    .card-body { padding: 25px; }
    .grid-info { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 20px; }
    .info-box { background: rgba(0,0,0,0.3); padding: 15px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05); }
    .info-label { font-size: 0.75rem; color: var(--text-muted); font-weight: 600; text-transform: uppercase; margin-bottom: 5px; }
    .info-value { font-size: 1.1rem; font-weight: bold; color: white; }
    .verdict-box { background: rgba(15, 23, 42, 0.6); border-left: 4px solid; padding: 15px; margin-top: 15px; font-style: italic; color: #e2e8f0; }
    .tech-section { background: rgba(0,0,0,0.2); padding: 15px; border-radius: 8px; margin-bottom: 15px; border: 1px solid rgba(255,255,255,0.05); }
    
    /* Style Khusus Tabel S/R */
    .sr-table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 0.9rem; }
    .sr-table td { padding: 8px; border-bottom: 1px solid var(--border); color: var(--text-main); }
    .sr-table tr:last-child td { border-bottom: none; }
    .sr-label { color: var(--text-muted); width: 40%; }
    .sr-val { font-weight: bold; text-align: right; color: var(--accent); }
</style>
""", unsafe_allow_html=True)

def parse_indo_json(text):
    try:
        clean = re.sub(r'```json\s*|\s*```', '', text).strip()
        return json.loads(clean)
    except:
        return {"summary": "Gagal parse.", "keputusan": "WAIT", "entry": "-", "sl": "-", "tp1": "-", "support_terdekat": "-", "resistance_terdekat": "-"}

def plot_tv_chart(df, symbol):
    if df is None: return None
    fig = go.Figure(data=[go.Candlestick(x=df['timestamp'], open=df['open'], high=df['high'], low=df['low'], close=df['close'])])
    # Tambah EMA 50 & 200 di Chart
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['EMA_50'], line=dict(color='yellow', width=1), name='EMA 50'))
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['EMA_200'], line=dict(color='white', width=2), name='EMA 200'))
    fig.update_layout(height=400, template="plotly_dark", title=f"{symbol} (H1)", xaxis_rangeslider_visible=False, paper_bgcolor="#1e293b", plot_bgcolor="#0f172a")
    return fig

def render_output_card(sym, data, mode):
    action = data.get('keputusan', 'WAIT').upper()
    bg_color = "#f43f5e" if action == "SHORT" else ("#10b981" if action == "LONG" else "#64748b")
    
    html = f"""
<div class="output-container">
    <div class="card-header futures-header">
        <div>
            <h2 style="margin:0; font-size: 1.5rem; color:white !important;">{sym} 
                <span style="background:{bg_color}; color:white; padding:2px 10px; border-radius:4px; font-size:0.6em; vertical-align:middle;">{action}</span>
            </h2>
            <small style="color:#94a3b8;">Strategy: AltaQuant v2.2 (Science-Based)</small>
        </div>
        <div style="text-align:right;">
            <div style="font-weight:bold; color:var(--futures-color);">AUDITED</div>
            <small style="color:#aaa;">GPT-OSS-120B</small>
        </div>
    </div>
    <div class="card-body">
        <div class="grid-info">
            <div class="info-box"><div class="info-label">Entry Zone</div><div class="info-value">{data.get('entry')}</div></div>
            <div class="info-box" style="border-color: rgba(239, 68, 68, 0.3);"><div class="info-label">Stop Loss (ATR)</div><div class="info-value" style="color:var(--danger)">{data.get('sl')}</div></div>
            <div class="info-box" style="border-color: rgba(16, 185, 129, 0.3);"><div class="info-label">Take Profit</div><div class="info-value" style="color:var(--secondary)">{data.get('tp1')} | {data.get('tp2')}</div></div>
        </div>
        <div class="tech-section">
            <div class="tech-title">KEY LEVELS (S/R)</div>
            <table class="sr-table">
                <tr>
                    <td class="sr-label">Resistance Terdekat</td>
                    <td class="sr-val">{data.get('resistance_terdekat', '-')}</td>
                </tr>
                <tr>
                    <td class="sr-label">Support Terdekat</td>
                    <td class="sr-val">{data.get('support_terdekat', '-')}</td>
                </tr>
            </table>
        </div>
        <div class="tech-section">
            <div class="tech-title">AUDIT REPORT</div>
            <div style="margin-bottom:8px;"><strong>Fundamental:</strong> {data.get('fundamental', '-')}</div>
            <div style="margin-bottom:8px;"><strong>Indikator (EMA/RSI):</strong> {data.get('tek_indikator', '-')}</div>
            <div><strong>Validasi Candle:</strong> {data.get('tek_candle', '-')}</div>
        </div>
        <div class="verdict-box" style="border-color: {bg_color};">
            <strong>FINAL VERDICT:</strong> "{data.get('summary', '-')}"
        </div>
    </div>
</div>
"""
    return html

# --- SIDEBAR & MAIN ---
with st.sidebar:
    st.header("Control Center")
    analysis_mode = st.selectbox("Mode", ["Futures (Scalping)", "Spot"])
    mode_input = st.radio("Input", ["Manual", "Auto-Scan"])
    sym_in = st.text_input("Pair", "BTC/USDT") if mode_input == "Manual" else None

st.title("AltaQuant Hybrid Core")

tab1, tab2 = st.tabs(["ANALISA", "HISTORY"])

with tab1:
    if st.button("JALANKAN ANALISA", type="primary"):
        with st.status("Hybrid AI Processing...", expanded=True) as status:
            # 1. Target Selection
            if mode_input == "Manual": targets = [{'symbol': sym_in}]
            else: 
                status.write("📡 Scanning Market...")
                targets = scan_dynamic_market()
            
            results = []
            for t in targets:
                sym = t['symbol']
                status.write(f"🔍 Processing {sym}...")
                
                # 2. Get Data & Context
                df, context, _ = get_ai_context_indo(sym)
                
                if df is not None:
                    # 3. Layer 1: Gemini (Sentiment)
                    sentiment = layer1_sentiment_analysis("Market News Simulation...")
                    
                    # 4. Layer 2: Screener (Opsional, kita skip biar cepat di demo ini)
                    
                    # 5. Layer 3: Auditor (GPT-OSS)
                    raw_json = layer3_final_decision(sym, context, sentiment, analysis_mode)
                    data = parse_indo_json(raw_json)
                    results.append({'symbol': sym, 'data': data, 'df': df, 'mode': analysis_mode})
            
            st.session_state['results'] = results
            status.update(label="Selesai!", state="complete")

    # Display
    if 'results' in st.session_state:
        for res in st.session_state['results']:
            st.plotly_chart(plot_tv_chart(res['df'], res['symbol']), use_container_width=True)
            st.markdown(render_output_card(res['symbol'], res['data'], res['mode']), unsafe_allow_html=True)