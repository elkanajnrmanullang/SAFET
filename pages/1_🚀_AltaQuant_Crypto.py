import streamlit as st
import plotly.graph_objects as go
import json
import re
from backend.crypto_data import get_ai_context_indo, scan_dynamic_market, get_market_overview
from backend.ai_engine import get_gemini_analysis
from backend.database import save_trade, get_history, update_outcome_and_learn, get_performance_stats

st.set_page_config(page_title="AltaQuant Pro", layout="wide")

# --- CSS Styling ---
st.markdown("""
<style>
    .metric-box {text-align: center; background: #1e293b; padding: 10px; border-radius: 8px; border: 1px solid #334155; margin-bottom: 10px;}
    .metric-val {font-size: 1.5rem; font-weight: bold; color: white;}
    .metric-lbl {font-size: 0.8rem; color: #94a3b8;}
    
    /* Card Styles */
    .output-container {border:1px solid #334155; border-radius:12px; overflow:hidden; margin-bottom:20px; background:#0f172a;}
    .card-header {padding: 15px 20px; font-weight:bold; font-size:1.2rem; display:flex; justify-content:space-between; align-items:center;}
    .card-body {padding: 20px;}
    
    /* Sections */
    .section-title {color: #94a3b8; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 1px; margin-top: 15px; margin-bottom: 5px; border-bottom: 1px solid #334155; padding-bottom: 5px;}
    .content-text {color: #e2e8f0; font-size: 0.95rem; line-height: 1.6;}
    
    /* Lists inside card */
    .tech-list {list-style-type: none; padding-left: 0;}
    .tech-list li {margin-bottom: 8px; padding-left: 15px; border-left: 2px solid #6366f1;}
    .tech-label {color: #a5b4fc; font-weight: 600;}
</style>
""", unsafe_allow_html=True)

# --- FUNGSI ---
def parse_indo_json(text):
    try:
        clean = re.sub(r'```json\s*|\s*```', '', text).strip()
        return json.loads(clean)
    except:
        return {
            "fundamental": "Gagal memuat fundamental.",
            "tek_indikator": "Data error.", "tek_chart": "-", "tek_candle": "-", "tek_lain": "-",
            "summary": text[:500], "keputusan": "WAIT", "entry": "-", "sl": "-", "tp1": "-", "tp2": "-"
        }

def plot_tv_chart(df, symbol):
    if df is None: return None
    fig = go.Figure(data=[go.Candlestick(x=df['timestamp'], open=df['open'], high=df['high'], low=df['low'], close=df['close'])])
    fig.update_layout(height=400, template="plotly_dark", title=f"{symbol} (H1)", xaxis_rangeslider_visible=False)
    return fig

# --- RENDER CARD FORMAT BARU (FIXED INDENTATION) ---
def render_output_card(sym, data):
    action = data.get('keputusan', 'WAIT').upper()
    
    # Warna Tema
    if "LONG" in action or "BUY" in action:
        theme_color = "#10b981" # Green
        bg_header = "rgba(16, 185, 129, 0.1)"
    elif "SHORT" in action or "SELL" in action:
        theme_color = "#ef4444" # Red
        bg_header = "rgba(239, 68, 68, 0.1)"
    else:
        theme_color = "#fbbf24" # Yellow
        bg_header = "rgba(251, 191, 36, 0.1)"

    # PERBAIKAN: HTML String dibuat rata kiri (tanpa indentasi) agar terbaca sebagai HTML oleh Markdown
    html = f"""
<div class="output-container" style="border-color: {theme_color};">
    <div class="card-header" style="background: {bg_header}; color: {theme_color};">
        <div>{sym} &nbsp; <span style="background:{theme_color}; color:white; padding:2px 8px; border-radius:4px; font-size:0.7em;">{action}</span></div>
        <div style="font-size:0.9rem;">Target: {data.get('tp1')}</div>
    </div>
    
    <div class="card-body">
        <div class="section-title">Fundamental</div>
        <div class="content-text">{data.get('fundamental', '-')}</div>
        
        <div class="section-title">Teknikal</div>
        <ul class="tech-list content-text">
            <li><span class="tech-label">1. Indikator:</span> {data.get('tek_indikator', '-')}</li>
            <li><span class="tech-label">2. Chart Pattern:</span> {data.get('tek_chart', '-')}</li>
            <li><span class="tech-label">3. Candle Pattern:</span> {data.get('tek_candle', '-')}</li>
            <li><span class="tech-label">4. Lainnya:</span> {data.get('tek_lain', '-')}</li>
        </ul>
        
        <div class="section-title">Summary & Execution</div>
        <div class="content-text" style="margin-bottom:15px;">{data.get('summary', '-')}</div>
        
        <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:10px; background:rgba(0,0,0,0.2); padding:10px; border-radius:8px;">
            <div style="text-align:center;">
                <div style="font-size:0.75rem; color:#94a3b8;">ENTRY</div>
                <div style="font-weight:bold; color:white;">{data.get('entry')}</div>
            </div>
            <div style="text-align:center;">
                <div style="font-size:0.75rem; color:#94a3b8;">STOP LOSS</div>
                <div style="font-weight:bold; color:#ef4444;">{data.get('sl')}</div>
            </div>
            <div style="text-align:center;">
                <div style="font-size:0.75rem; color:#94a3b8;">TAKE PROFIT</div>
                <div style="font-weight:bold; color:#10b981;">{data.get('tp1')} | {data.get('tp2')}</div>
            </div>
        </div>
    </div>
</div>
"""
    return html

# --- SIDEBAR ---
with st.sidebar:
    st.header("🎮 Control Center")
    mode = st.radio("Mode", ["Manual Input", "Auto-Discovery"])
    sym_in = st.text_input("Simbol", "BTC/USDT").upper() if mode == "Manual Input" else None
    
    st.markdown("---")
    st.header("📈 Performance Stats")
    stats = get_performance_stats()
    c1, c2 = st.columns(2)
    with c1: st.markdown(f'<div class="metric-box"><div class="metric-val">{stats["win_rate"]:.1f}%</div><div class="metric-lbl">Win Rate</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-box"><div class="metric-val">{stats["total"]}</div><div class="metric-lbl">Total Trades</div></div>', unsafe_allow_html=True)

# --- MAIN ---
st.title("AltaQuant v3.3: Hybrid Intelligence")

if 'results' not in st.session_state: st.session_state['results'] = []

if not st.session_state['results'] and not st.session_state.get('btn_clicked', False):
    ov = get_market_overview()
    st.info("Pastikan VPN AKTIF untuk koneksi Binance & Roboflow.")
    c1, c2 = st.columns(2)
    with c1: st.markdown(f'<div class="metric-box"><div class="metric-lbl">BTC Price</div><div class="metric-val">${ov["btc_price"]:.2f}</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-box"><div class="metric-lbl">System</div><div class="metric-val" style="color:#10b981">READY</div></div>', unsafe_allow_html=True)

tab1, tab2 = st.tabs(["🚀 ANALISA", "📜 HISTORY"])

with tab1:
    if st.button("MULAI ANALISA", type="primary"):
        st.session_state['btn_clicked'] = True
        with st.status("🔍 Menjalankan Hybrid Scan...", expanded=True) as status:
            targets = [{'symbol': sym_in, 'bias': 'MANUAL'}] if mode == "Manual Input" else scan_dynamic_market()
            
            if not targets and mode != "Manual Input":
                status.write("Pasar Konsolidasi/Koneksi Lambat. Mengambil Top Cap.")
                targets = [{'symbol': 'BTC/USDT', 'bias': 'NEUTRAL'}, {'symbol': 'ETH/USDT', 'bias': 'NEUTRAL'}, {'symbol': 'SOL/USDT', 'bias': 'NEUTRAL'}]
            elif not targets and mode == "Manual Input":
                 st.error("Gagal koneksi atau simbol salah.")

            res_temp = []
            
            for t in targets:
                sym = t['symbol']
                status.write(f"Menganalisa {sym} (Vision + Math)...")
                
                df, context, poc = get_ai_context_indo(sym)
                
                if df is not None:
                    prompt = f"""
                    Role: Professional Institutional Trader. Task: Analisa {sym}. Bias: {t['bias']}.
                    Data: {context}.
                    
                    STRATEGI (INSTITUTIONAL):
                    1. Trend is King: Gunakan EMA 200 sebagai batas Bull/Bear.
                    2. RSI 14: Perhatikan level 50 sebagai support di uptrend dan resistance di downtrend.
                    3. MACD: Gunakan sebagai konfirmasi momentum (Histogram positif/negatif).
                    4. Volume Profile (POC): Entry ideal di dekat POC dalam arah tren.
                    
                    OUTPUT WAJIB JSON:
                    {{
                        "fundamental": "Analisa fundamental singkat...",
                        "tek_indikator": "Analisa Indikator...",
                        "tek_chart": "Analisa Chart Pattern...",
                        "tek_candle": "Analisa Candle Pattern...",
                        "tek_lain": "Analisa Support/Resist/Fibonacci...",
                        "summary": "Kesimpulan akhir...",
                        "keputusan": "LONG/SHORT/WAIT",
                        "entry": "Harga", "sl": "Harga", "tp1": "Harga", "tp2": "Harga",
                        "alasan": "Alasan singkat untuk history"
                    }}
                    """
                    try:
                        raw = get_gemini_analysis(prompt)
                        parsed = parse_indo_json(raw)
                        res_temp.append({'symbol': sym, 'data': parsed, 'df': df, 'bias': t['bias']})
                    except Exception as e:
                        st.error(f"Gagal analisa {sym}: {e}")
            
            st.session_state['results'] = res_temp
            status.update(label="Selesai!", state="complete")

    for res in st.session_state['results']:
        sym = res['symbol']
        st.plotly_chart(plot_tv_chart(res['df'], sym), use_container_width=True)
        # PENTING: unsafe_allow_html=True wajib ada agar HTML ter-render
        st.markdown(render_output_card(sym, res['data']), unsafe_allow_html=True)
        
        if st.button(f"💾 Simpan {sym}", key=f"s_{sym}"):
            save_trade(sym, res['data'])
            st.success("Disimpan!")
        st.divider()

# --- TAB 2: HISTORY ---
with tab2:
    st.header("Trade History")
    history = get_history()
    
    if not history:
        st.info("Belum ada data history. Lakukan analisa dan simpan trade.")
    else:
        for row in history:
            with st.expander(f"{row['symbol']} ({row['action']}) - {row['status']}"):
                st.write(f"**Alasan:** {row['reason']}")
                st.write(f"**Entry:** {row['entry']} | **SL:** {row['sl']} | **TP:** {row['tp']}")
                
                if row['status'] == 'OPEN':
                    c1, c2 = st.columns(2)
                    if c1.button("WIN (Belajar Pola)", key=f"w_{row['id']}"):
                        note = st.text_input("Kenapa Win?", "Sesuai Analisa", key=f"nw_{row['id']}")
                        if note: 
                            update_outcome_and_learn(row['id'], 'WIN', note)
                            st.rerun()
                    
                    if c2.button("LOSS (Hindari Error)", key=f"l_{row['id']}"):
                        note = st.text_input("Kenapa Loss?", "Market Berbalik", key=f"nl_{row['id']}")
                        if note:
                            update_outcome_and_learn(row['id'], 'LOSS', note)
                            st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)