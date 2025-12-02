import streamlit as st
import plotly.graph_objects as go
import json
import re
import time
from backend.crypto_data import get_ai_context_indo, scan_dynamic_market, get_market_overview
from backend.ai_engine import get_gemini_analysis
from backend.database import save_trade, get_history, update_outcome, update_outcome_and_learn

st.set_page_config(page_title="AltaQuant Pro", layout="wide")

# --- CSS (Tetap) ---
st.markdown("""
<style>
    :root {--primary:#6366f1; --bg:#0f172a; --card:#1e293b; --border:#334155;}
    .output-container {border:1px solid var(--border); border-radius:12px; overflow:hidden; margin-bottom:30px; background:var(--bg);}
    .output-header {padding:15px 20px; display:flex; justify-content:space-between; align-items:center;}
    .header-long {background:linear-gradient(90deg, rgba(16,185,129,0.2), transparent); border-bottom:1px solid #10b981;}
    .header-short {background:linear-gradient(90deg, rgba(239,68,68,0.2), transparent); border-bottom:1px solid #ef4444;}
    .grid-info {display:grid; grid-template-columns:repeat(3,1fr); gap:10px; padding:20px;}
    .info-item {background:rgba(0,0,0,0.3); padding:10px; border-radius:6px; border:1px solid var(--border);}
    .lbl {font-size:0.75rem; color:#94a3b8; text-transform:uppercase;}
    .val {font-size:1.1rem; font-weight:bold; color:#f8fafc;}
    .analysis-text {padding:0 20px 20px 20px; color:#cbd5e1; font-size:0.95rem; line-height:1.6;}
    .verdict {background:#0f172a; padding:15px; border-left:4px solid; margin:0 20px 20px 20px;}
    .hero-metric {background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); padding: 20px; border-radius: 10px; border: 1px solid #334155; text-align: center;}
    .metric-val {font-size: 2rem; font-weight: 800; color: white;}
    .metric-lbl {font-size: 0.9rem; color: #94a3b8; text-transform: uppercase;}
    .hist-card {background: #0f172a; padding: 15px; margin-bottom: 10px; border-radius: 8px; border: 1px solid #334155;}
</style>
""", unsafe_allow_html=True)

# --- FUNGSI ---
def parse_indo_json(text):
    try:
        clean = re.sub(r'```json\s*|\s*```', '', text).strip()
        return json.loads(clean)
    except:
        return {"fundamental":"Error","teknikal":"Error","chart_pattern":"-","candle_pattern":"-","keputusan":"WAIT","entry":"-","sl":"-","tp1":"-","tp2":"-","alasan":text[:200]}

def plot_tv_chart(df, symbol):
    fig = go.Figure(data=[go.Candlestick(x=df['timestamp'], open=df['open'], high=df['high'], low=df['low'], close=df['close'])])
    last = df['close'].iloc[-1]
    fig.add_hline(y=last, line_dash="dash", line_color="white", annotation_text=f" Price: {last}")
    fig.update_layout(height=350, margin=dict(t=30,b=0,l=0,r=0), xaxis_rangeslider_visible=False, paper_bgcolor="#0f172a", plot_bgcolor="#0f172a", xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor="#1e293b"), title=dict(text=f"{symbol} (H1)", font=dict(color="white")))
    return fig

# --- RENDER CARD ---
def render_altaquant_card(symbol, data, bias):
    action = data.get('keputusan', 'WAIT').upper()
    is_long = "LONG" in action or "BUY" in action
    theme = "#10b981" if is_long else "#ef4444"
    header_cls = "header-long" if is_long else "header-short"
    
    tp_display = f"<div style='font-size:0.9em;'>TP1: <span style='color:#fff'>{data.get('tp1', '-')}</span></div><div style='font-size:0.9em;'>TP2: <span style='color:#fff'>{data.get('tp2', '-')}</span></div>"
    
    html = f"""
    <div class="output-container">
        <div class="output-header {header_cls}">
            <div><h2 style="margin:0; color:white;">{symbol} <span style="background:{theme}; padding:2px 8px; border-radius:4px; font-size:0.7em;">{action}</span></h2></div>
            <div style="text-align:right;"><span style="color:{theme}; font-weight:bold;">ALGO BIAS: {bias}</span></div>
        </div>
        <div class="grid-info">
            <div class="info-item"><div class="lbl">Entry</div><div class="val">{data.get('entry')}</div></div>
            <div class="info-item" style="border-color:#ef4444"><div class="lbl">Stop Loss</div><div class="val" style="color:#ef4444">{data.get('sl')}</div></div>
            <div class="info-item" style="border-color:#10b981"><div class="lbl">Targets</div><div class="val" style="color:#10b981">{tp_display}</div></div>
        </div>
        <div class="analysis-text">
            <strong>🌍 Fundamental:</strong><br>{data.get('fundamental')}<br><br>
            <strong>📊 Teknikal (RSI 14 + MACD):</strong><br>{data.get('teknikal')}<br>
            <em>Chart: {data.get('chart_pattern')} | Candle: {data.get('candle_pattern')}</em>
        </div>
        <div class="verdict" style="border-color:{theme};"><strong>🤖 Kesimpulan AI:</strong> "{data.get('alasan')}"</div>
    </div>
    """
    return html

# --- MAIN ---
st.title("AltaQuant: Institutional Engine")
tab1, tab2 = st.tabs(["🚀 ANALISA", "📜 HISTORY"])

with tab1:
    if 'results' not in st.session_state: st.session_state['results'] = []
    
    with st.sidebar:
        st.header("Kontrol")
        mode = st.radio("Mode", ["Manual Input", "Auto-Discovery"])
        sym_in = st.text_input("Simbol", "BTC/USDT").upper() if mode == "Manual Input" else None
        btn = st.button("MULAI ANALISA", type="primary")

    if not st.session_state['results'] and not btn:
        ov = get_market_overview()
        st.info("Pastikan VPN AKTIF.")
        c1, c2 = st.columns(2)
        with c1: st.markdown(f'<div class="hero-metric"><div class="metric-lbl">BTC Price</div><div class="metric-val">${ov["btc_price"]:.2f}</div></div>', unsafe_allow_html=True)
        with c2: st.markdown(f'<div class="hero-metric"><div class="metric-lbl">System</div><div class="metric-val" style="color:#10b981">READY</div></div>', unsafe_allow_html=True)

    if btn:
        st.session_state['results'] = []
        with st.status("🔄 Menghubungkan ke Binance...", expanded=True) as status:
            targets = [{'symbol': sym_in, 'bias': 'MANUAL'}] if mode == "Manual Input" else scan_dynamic_market()
            
            if not targets and mode != "Manual Input":
                status.write("Pasar Konsolidasi. Mengambil Top Cap.")
                targets = [{'symbol': 'BTC/USDT', 'bias': 'NEUTRAL'}, {'symbol': 'ETH/USDT', 'bias': 'NEUTRAL'}, {'symbol': 'SOL/USDT', 'bias': 'NEUTRAL'}]
            elif not targets and mode == "Manual Input":
                 st.error("Gagal koneksi.")

            res_temp = []
            prog = st.progress(0)
            
            for idx, t in enumerate(targets):
                sym = t['symbol']
                prog.progress((idx+1)*int(100/len(targets)))
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
                    fundamental, teknikal, chart_pattern, candle_pattern, keputusan (LONG/SHORT), entry, sl, tp1, tp2, alasan.
                    """
                    raw = get_gemini_analysis(prompt)
                    res_temp.append({'symbol': sym, 'data': parse_indo_json(raw), 'df': df, 'bias': t['bias']})
            
            st.session_state['results'] = res_temp
            prog.empty()
            status.update(label="Selesai!", state="complete")

    for res in st.session_state['results']:
        sym = res['symbol']
        st.plotly_chart(plot_tv_chart(res['df'], sym), use_container_width=True)
        st.markdown(render_altaquant_card(sym, res['data'], res['bias']), unsafe_allow_html=True)
        if st.button(f"💾 Simpan {sym}", key=f"s_{sym}"):
            save_trade(sym, res['data'])
            st.success("Disimpan!")
        st.divider()

# Tab 2 History (Sama)
with tab2:
    st.header("History Trade")
    history = get_history()
    for row in history:
        with st.container():
            c1, c2, c3 = st.columns([2, 4, 2])
            with c1: st.write(f"**{row['symbol']}** ({row['action']})")
            with c2: st.write(f"{row['reason']}")
            with c3:
                if row['status'] == 'OPEN':
                    if st.button("WIN", key=f"w_{row['id']}"):
                        update_outcome_and_learn(row['id'], 'WIN', "Sesuai Analisa")
                        st.rerun()
                    if st.button("LOSS", key=f"l_{row['id']}"):
                        update_outcome_and_learn(row['id'], 'LOSS', "Tidak Sesuai")
                        st.rerun()
                else:
                    st.write(f"Status: {row['status']}")
            st.markdown("---")