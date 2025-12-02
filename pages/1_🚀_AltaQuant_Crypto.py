import streamlit as st
import plotly.graph_objects as go
import json
import re
import time
import traceback
from backend.crypto_data import get_ai_context_indo, scan_dynamic_market, get_market_overview
from backend.ai_engine import get_gemini_analysis
from backend.database import save_trade, get_history, update_outcome, update_outcome_and_learn, get_performance_stats

st.set_page_config(page_title="AltaQuant Pro V6.1", layout="wide")

# --- CSS ---
st.markdown("""
<style>
    :root {--primary:#6366f1; --bg:#0f172a; --card:#1e293b; --border:#334155; --success:#10b981; --danger:#ef4444; --gold:#f59e0b; --neutral:#94a3b8;}
    p, li, span {line-height: 1.6 !important; letter-spacing: 0.3px;}
    .output-container {border:1px solid var(--border); border-radius:12px; overflow:hidden; margin-bottom:30px; background:var(--bg);}
    .output-header {padding:15px 25px; display:flex; justify-content:space-between; align-items:center; border-bottom: 1px solid rgba(255,255,255,0.05);}
    .header-long {background:linear-gradient(90deg, rgba(16,185,129,0.1), transparent); border-left: 5px solid var(--success);}
    .header-short {background:linear-gradient(90deg, rgba(239,68,68,0.1), transparent); border-left: 5px solid var(--danger);}
    .header-wait {background:linear-gradient(90deg, rgba(148,163,184,0.1), transparent); border-left: 5px solid var(--neutral);}
    .grid-info {display:grid; grid-template-columns:repeat(3,1fr); gap:15px; padding:20px 25px;}
    .info-item {background:rgba(255,255,255,0.03); padding:12px; border-radius:8px; border:1px solid var(--border);}
    .lbl {font-size:0.7rem; color:#94a3b8; text-transform:uppercase; letter-spacing:1px; margin-bottom: 4px;}
    .val {font-size:1.1rem; font-weight:bold; color:#f8fafc;}
    .analysis-section {padding: 0 25px 20px 25px; display: grid; gap: 20px;}
    .analysis-box {background: rgba(0,0,0,0.2); border-radius: 8px; padding: 15px; border: 1px solid rgba(255,255,255,0.05);}
    .analysis-title {color: var(--gold); font-size: 0.9rem; font-weight: bold; margin-bottom: 10px; display: flex; align-items: center; gap: 8px;}
    .analysis-content {color: #cbd5e1; font-size: 0.95rem; white-space: pre-line;} 
    .clean-list {margin: 0; padding-left: 20px;} .clean-list li {margin-bottom: 6px;}
    .verdict {background:#0f172a; padding:20px 25px; border-top:1px solid var(--border); margin-top: 10px;}
    .inst-badge {padding: 4px 10px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; margin-right: 5px; display: inline-block;}
    .badge-bull {background: rgba(16,185,129,0.2); color: var(--success); border: 1px solid var(--success);}
    .badge-bear {background: rgba(239,68,68,0.2); color: var(--danger); border: 1px solid var(--danger);}
    .badge-neu {background: rgba(255,255,255,0.1); color: #cbd5e1; border: 1px solid #cbd5e1;}
    .hist-card {background: #0f172a; padding: 15px; margin-bottom: 10px; border-radius: 8px; border: 1px solid #334155;}
    .hero-metric {background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); padding: 20px; border-radius: 10px; border: 1px solid #334155; text-align: center;}
    .metric-val {font-size: 2rem; font-weight: 800; color: white;}
    .metric-lbl {font-size: 0.9rem; color: #94a3b8; text-transform: uppercase;}
</style>
""", unsafe_allow_html=True)

# --- HELPERS ---
def parse_json(text):
    try:
        clean = re.sub(r'```json\s*|\s*```', '', text).strip()
        return json.loads(clean)
    except Exception as e:
        return {"fundamental": f"Gagal Parsing JSON: {str(e)}", "teknikal":"-", "keputusan":"WAIT", "entry":"-", "sl":"-", "tp1":"-", "tp2":"-", "alasan": text[:500]}

def clean_text_output(data_input):
    if isinstance(data_input, dict):
        html_list = '<ul class="clean-list">'
        for k, v in data_input.items():
            clean_key = k.replace("_", " ").title()
            html_list += f"<li><strong>{clean_key}:</strong> {v}</li>"
        html_list += "</ul>"
        return html_list
    elif isinstance(data_input, list):
        html_list = '<ul class="clean-list">'
        for item in data_input: html_list += f"<li>{item}</li>"
        html_list += "</ul>"
        return html_list
    else:
        val = str(data_input) if data_input is not None else "-"
        return val.replace("\n", "<br>")

def plot_chart(df, symbol, poc_price):
    fig = go.Figure(data=[go.Candlestick(x=df['timestamp'], open=df['open'], high=df['high'], low=df['low'], close=df['close'])])
    last = df['close'].iloc[-1]
    fig.add_hline(y=last, line_dash="dash", line_color="white", annotation_text=f" Price: {last}")
    if poc_price > 0:
        fig.add_hline(y=poc_price, line_color="#facc15", line_width=2, annotation_text=f" POC (Volume): {poc_price:.2f}", annotation_position="bottom right")
    fig.update_layout(height=400, margin=dict(t=30,b=0,l=0,r=0), xaxis_rangeslider_visible=False, paper_bgcolor="#0f172a", plot_bgcolor="#0f172a", xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor="#1e293b"), title=dict(text=f"{symbol} (H1) + Volume Profile", font=dict(color="white")))
    return fig

# --- RENDER CARD ---
def render_card(symbol, data, bias, extra_data):
    raw_action = str(data.get('keputusan', 'WAIT')).upper()
    if "LONG" in raw_action: 
        action = "LONG (MARKET)"
        theme = "#10b981"
        header_cls = "header-long"
    elif "SHORT" in raw_action:
        action = "SHORT (MARKET)"
        theme = "#ef4444"
        header_cls = "header-short"
    else:
        action = "WAIT"
        theme = "#94a3b8"
        header_cls = "header-wait"
    
    btc_trend = extra_data.get('btc_trend', 'UNKNOWN')
    sentiment = extra_data.get('sentiment', 'NEUTRAL')
    
    btc_cls = "badge-bull" if btc_trend == "BULLISH" else "badge-bear"
    sent_cls = "badge-bull" if sentiment == "POSITIVE" else "badge-bear" if sentiment == "NEGATIVE" else "badge-neu"
    
    clean_fund = clean_text_output(data.get('fundamental'))
    clean_tech = clean_text_output(data.get('teknikal'))
    
    entry_val = data.get('entry') if data.get('entry') else "-"
    sl_val = data.get('sl') if data.get('sl') else "-"
    tp1_val = data.get('tp1') if data.get('tp1') else "-"
    tp2_val = data.get('tp2') if data.get('tp2') else "-"

    html = f"""
<div class="output-container">
<div class="output-header {header_cls}">
<div>
<h2 style="margin:0; color:white; font-size:1.6rem;">{symbol} <span style="background:{theme}; padding:4px 12px; border-radius:6px; font-size:0.6em; vertical-align:middle;">{action}</span></h2>
<div style="margin-top:8px;">
<span class="inst-badge {btc_cls}">BTC: {btc_trend}</span>
<span class="inst-badge {sent_cls}">NEWS: {sentiment}</span>
</div>
</div>
<div style="text-align:right;">
<span style="color:{theme}; font-weight:bold; font-size:1.2em; letter-spacing:1px;">BIAS: {bias}</span><br>
<small style="color:#94a3b8; font-size:0.75em;">INSTITUTIONAL V6.1</small>
</div>
</div>
<div class="grid-info">
<div class="info-item"><div class="lbl">Entry Zone (MARKET)</div><div class="val">{entry_val}</div></div>
<div class="info-item" style="border-color:#ef4444"><div class="lbl">Stop Loss</div><div class="val" style="color:#ef4444">{sl_val}</div></div>
<div class="info-item" style="border-color:#10b981"><div class="lbl">Take Profit</div><div class="val" style="color:#10b981">1. {tp1_val}<br>2. {tp2_val}</div></div>
</div>
<div class="analysis-section">
<div class="analysis-box">
<div class="analysis-title">🌍 FUNDAMENTAL & NEWS</div>
<div class="analysis-content">{clean_fund}</div>
</div>
<div class="analysis-box">
<div class="analysis-title">📊 TECHNICAL SOP (H1 Breakdown)</div>
<div class="analysis-content">{clean_tech}</div>
<div style="margin-top:10px; border-top:1px solid rgba(255,255,255,0.1); padding-top:8px; font-size:0.85em; color:#94a3b8;">
<strong>Patterns:</strong> {data.get('chart_pattern', '-')} | {data.get('candle_pattern', '-')}
</div>
</div>
<div class="analysis-box">
<div class="analysis-title">📰 NEWS SENTIMENT</div>
<div class="analysis-content">{str(extra_data.get('news', 'Tidak ada data berita.')).replace(' - ', '<br>• ')}</div>
</div>
</div>
<div class="verdict" style="border-color:{theme};">
<strong style="color:{theme};">🤖 MASTER VERDICT:</strong><br>
<span style="color:#e2e8f0; font-size:1.05rem; font-style:italic;">"{data.get('alasan')}"</span>
</div>
</div>
"""
    return html

# --- MAIN ---
st.title("AltaQuant V6: Final Institutional Engine")
tab1, tab2 = st.tabs(["🚀 ANALISA SOP", "📊 SCOREBOARD"])

with tab1:
    with st.sidebar:
        st.header("Command Center")
        mode = st.radio("Mode Operasi", ["Manual Input", "Auto-Discovery"])
        sym_in = st.text_input("Simbol Aset", "BTC/USDT").upper() if mode == "Manual Input" else None
        st.markdown("---")
        st.info("💡 **V6.1 Features:**\n- DEBUG MODE ACTIVATED\n- Anti-Silent Crash\n- Real-time Error Log")
        btn = st.button("RUN ANALYSIS", type="primary")

    if 'results' not in st.session_state: st.session_state['results'] = []

    if not st.session_state['results'] and not btn:
        ov = get_market_overview()
        c1, c2 = st.columns(2)
        with c1: st.markdown(f'<div class="hero-metric"><div class="metric-lbl">BTC PRICE</div><div class="metric-val">${ov["btc_price"]:.2f}</div><div class="metric-lbl" style="color:{"#10b981" if ov["btc_change"]>0 else "#ef4444"}">{ov["btc_change"]:.2f}%</div></div>', unsafe_allow_html=True)
        with c2: st.markdown(f'<div class="hero-metric"><div class="metric-lbl">ETH PRICE</div><div class="metric-val">${ov["eth_price"]:.2f}</div><div class="metric-lbl" style="color:{"#10b981" if ov["eth_change"]>0 else "#ef4444"}">{ov["eth_change"]:.2f}%</div></div>', unsafe_allow_html=True)
        st.info("👋 **Sistem Siap.**")

    if btn:
        st.session_state['results'] = []
        with st.status("🔄 Menjalankan AltaQuant V6 Core...", expanded=True) as status:
            targets = []
            
            if mode == "Auto-Discovery":
                status.write("1. Scanning High-Prob Candidates...")
                try:
                    targets = scan_dynamic_market() 
                    if not targets: st.error("Fatal Error: Scanner gagal.")
                except Exception as e: 
                    st.error(f"❌ Scanner Error: {e}")
                    # EMERGENCY FALLBACK UI
                    targets = [{'symbol': 'BTC/USDT', 'bias': 'EMERGENCY', 'poc': 0}]
            else:
                targets = [{'symbol': sym_in, 'bias': 'MANUAL', 'poc': 0}]

            results = []
            if targets:
                prog = st.progress(0)
                for idx, t in enumerate(targets):
                    sym = t['symbol']
                    poc_scan = t.get('poc', 0)
                    prog.progress((idx+1)*int(100/len(targets)))
                    
                    status.write(f"Analisa {sym}...")
                    
                    # --- DEBUGGING BLOCK (INI KUNCI PERBAIKANNYA) ---
                    try:
                        # 1. Fetch Data Backend
                        df, context, poc_final, extra_data = get_ai_context_indo(sym, poc_scan)
                        
                        if df is None:
                            st.error(f"❌ Data Gagal Diambil untuk {sym}. Cek Koneksi.")
                            continue
                            
                        current_price = df['close'].iloc[-1]
                        
                        # 2. Prompt AI
                        prompt = f"""
                        Role: Institutional Technical Analyst.
                        Tugas: Analisa {sym} dengan SOP KONTEKSTUAL (Trend -> Pattern -> Candle).
                        
                        [DATA MARKET]:
                        HARGA SEKARANG: {current_price}
                        {context}
                        
                        INSTRUKSI BERPIKIR (SOP):
                        1. **LIHAT GAMBAR BESAR (24H OHLC):**
                           - Perhatikan data 'DATA CHART 24 JAM'. Apakah membentuk pola? (Flag, Channel, Consolidation).
                        
                        2. **CARI KONFIRMASI CANDLE:**
                           - Apakah candle terakhir valid sebagai trigger?
                        
                        3. **KEPUTUSAN (MARKET ORDER):**
                           - Sikat (LONG/SHORT) di harga {current_price}.
                           - Jika Auto-Discovery: WAJIB PILIH arah.
                        
                        OUTPUT JSON:
                        - fundamental: Ringkasan singkat.
                        - teknikal: Analisa teknikal singkat.
                        - chart_pattern: Pola grafik 24h.
                        - candle_pattern: Pola candle trigger.
                        - keputusan: "LONG" atau "SHORT".
                        - entry: "{current_price}".
                        - sl: Angka Stop Loss.
                        - tp1: Angka Target 1.
                        - tp2: Angka Target 2.
                        - alasan: Sintesa akhir.
                        """
                        
                        # 3. Call AI
                        raw = get_gemini_analysis(prompt)
                        
                        # 4. Parse JSON
                        parsed = parse_json(raw)
                        
                        # 5. Append Result
                        results.append({'symbol': sym, 'data': parsed, 'df': df, 'bias': t['bias'], 'poc': poc_final, 'extra': extra_data})
                    
                    except Exception as e:
                        # JIKA ERROR, TAMPILKAN DI LAYAR AGAR USER TAHU
                        st.error(f"⚠️ Error pada {sym}: {str(e)}")
                        print(f"DEBUG ERROR: {traceback.format_exc()}") # Print ke terminal juga
                        continue
                
                st.session_state['results'] = results
                prog.empty()
                status.update(label="Selesai!", state="complete")

    for res in st.session_state['results']:
        sym = res['symbol']
        st.plotly_chart(plot_chart(res['df'], sym, res['poc']), use_container_width=True)
        st.markdown(render_card(sym, res['data'], res['bias'], res['extra']), unsafe_allow_html=True)
        
        c_save, c_dummy = st.columns([1,4])
        with c_save:
            if st.button(f"💾 Simpan ke Jurnal", key=f"s_{sym}"):
                save_trade(sym, res['data'])
                st.success("Tersimpan!")
        st.divider()

with tab2:
    st.header("📊 Performance Dashboard")
    
    stats = get_performance_stats()
    
    m1, m2, m3, m4 = st.columns(4)
    with m1: st.metric("Total Trades", f"{stats['total']}", help="Total trade yang sudah selesai")
    with m2: st.metric("Win Rate", f"{stats['win_rate']:.1f}%", help="Persentase kemenangan")
    with m3: st.metric("Wins", f"{stats['wins']} ✅")
    with m4: st.metric("Losses", f"{stats['losses']} ❌")
        
    if stats['total'] > 0:
        st.write("### Akurasi Sistem:")
        st.progress(stats['win_rate'] / 100)
    
    st.markdown("---")
    st.subheader("📜 Trade Log")
    
    history = get_history()
    
    for row in history:
        with st.container():
            status_color = "#10b981" if row['status'] == 'WIN' else "#ef4444" if row['status'] == 'LOSS' else "#334155"
            border_style = f"border-left: 5px solid {status_color};"
            
            st.markdown(f'<div class="hist-card" style="{border_style}">', unsafe_allow_html=True)
            col1, col2, col3 = st.columns([2, 4, 2])
            
            with col1:
                st.subheader(row['symbol'])
                st.caption(row['timestamp'][:16])
                st.markdown(f'<span style="background:{status_color}; padding:2px 8px; border-radius:4px; font-weight:bold; font-size:0.8em;">{row["status"]}</span>', unsafe_allow_html=True)
                
            with col2:
                st.write(f"**Setup:** {row['reason']}")
                if row['outcome_note']: st.info(f"Evaluasi: {row['outcome_note']}")
                    
            with col3:
                if row['status'] == 'OPEN':
                    c1_in, c2_in = st.columns(2)
                    with c1_in:
                        if st.button("WIN ✅", key=f"w{row['id']}"):
                            update_outcome_and_learn(row['id'], 'WIN', "Sesuai Analisa")
                            st.rerun()
                    with c2_in:
                        if st.button("LOSS ❌", key=f"l{row['id']}"):
                            st.session_state[f"fail_{row['id']}"] = True
                    
                    if st.session_state.get(f"fail_{row['id']}"):
                        note = st.text_input("Kenapa Loss?", key=f"n{row['id']}")
                        if st.button("Simpan", key=f"s{row['id']}"):
                            update_outcome_and_learn(row['id'], 'LOSS', note)
                            st.session_state[f"fail_{row['id']}"] = False
                            st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)