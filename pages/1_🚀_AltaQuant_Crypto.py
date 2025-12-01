import streamlit as st
import plotly.graph_objects as go
import json
import re
import time
from backend.crypto_data import get_ai_context_indo, scan_dynamic_market, get_market_overview
from backend.ai_engine import get_gemini_analysis
# FIX IMPORT HERE
from backend.database import save_trade, get_history, update_outcome, update_outcome_and_learn

st.set_page_config(page_title="AltaQuant Pro", layout="wide")

# --- CSS STYLES ---
st.markdown("""
<style>
    :root {
        --primary: #6366f1; --secondary: #10b981; --accent: #f59e0b; --danger: #ef4444;
        --bg-dark: #0f172a; --bg-card: #1e293b; --text-main: #f8fafc; --text-muted: #94a3b8; --border: #334155;
        --futures-color: #f43f5e; --spot-color: #34d399;
    }
    .output-container { border: 1px solid var(--border); border-radius: 12px; overflow: hidden; margin-bottom: 40px; background-color: var(--bg-dark); }
    .output-header { padding: 15px 25px; display: flex; justify-content: space-between; align-items: center; }
    .header-active { background: linear-gradient(90deg, rgba(52, 211, 153, 0.2), transparent); border-bottom: 1px solid var(--spot-color); }
    .header-short { background: linear-gradient(90deg, rgba(244, 63, 94, 0.2), transparent); border-bottom: 1px solid var(--futures-color); }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; margin-left: 10px; color: #000; }
    h2 { margin: 0; font-size: 1.5rem; color: var(--text-main); font-weight: 800; }
    .output-body { padding: 25px; }
    .grid-info { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 20px; }
    .info-box { background: rgba(0, 0, 0, 0.2); padding: 15px; border-radius: 8px; border: 1px solid var(--border); }
    .info-label { font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase; margin-bottom: 5px; }
    .info-value { font-size: 1.1rem; font-weight: bold; color: white; }
    .verdict-box { background: rgba(15, 23, 42, 0.6); border-left: 4px solid; padding: 15px; margin-top: 20px; font-style: italic; color: var(--text-muted); }
    .analysis-section { margin-bottom: 20px; color: var(--text-main); }
    .analysis-title { color: var(--primary); font-weight: 600; margin-bottom: 5px; font-size: 1rem; }
    
    /* Dashboard & History */
    .hero-metric {background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); padding: 20px; border-radius: 10px; border: 1px solid #334155; text-align: center;}
    .metric-val {font-size: 2rem; font-weight: 800; color: white;}
    .metric-lbl {font-size: 0.9rem; color: #94a3b8; text-transform: uppercase;}
    
    .hist-card {background: #0f172a; padding: 15px; border-radius: 8px; border: 1px solid #334155; margin-bottom: 15px;}
    .status-win {color: #10b981; font-weight: bold; border: 1px solid #10b981; padding: 2px 8px; border-radius: 4px;}
    .status-loss {color: #ef4444; font-weight: bold; border: 1px solid #ef4444; padding: 2px 8px; border-radius: 4px;}
</style>
""", unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
def parse_indo_json(text):
    try:
        clean = re.sub(r'```json\s*|\s*```', '', text).strip()
        return json.loads(clean)
    except:
        return {
            "fundamental": "Gagal Parsing", "teknikal": "Gagal Parsing", 
            "chart_pattern": "-", "candle_pattern": "-", 
            "keputusan": "WAIT", "entry": "-", "sl": "-", 
            "tp1": "-", "tp2": "-", 
            "alasan": text[:300]
        }

def plot_tv_chart(df, symbol):
    fig = go.Figure(data=[go.Candlestick(x=df['timestamp'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], increasing_line_color='#26a69a', decreasing_line_color='#ef5350')])
    last = df['close'].iloc[-1]
    fig.add_hline(y=last, line_dash="dash", line_color="white", annotation_text=f" Price: {last}")
    fig.update_layout(height=350, margin=dict(t=30, b=0, l=0, r=0), xaxis_rangeslider_visible=False, paper_bgcolor="#0f172a", plot_bgcolor="#0f172a", xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor="#1e293b"), title=dict(text=f"{symbol} (H1)", font=dict(color="white")))
    return fig

# --- RENDER CARD ---
def render_altaquant_card(symbol, data, bias):
    action = data.get('keputusan', 'WAIT').upper()
    is_long = "LONG" in action or "BUY" in action
    theme_color = "#34d399" if is_long else "#f43f5e"
    header_class = "header-active" if is_long else "header-short"
    badge_bg = theme_color
    
    tp_display = f"""
    <div style="font-size:0.9em;">TP1: <span style="color:#fff">{data.get('tp1', '-')}</span></div>
    <div style="font-size:0.9em;">TP2: <span style="color:#fff">{data.get('tp2', '-')}</span></div>
    """
    
    html = f"""
    <div class="output-container">
        <div class="output-header {header_class}">
            <div><h2>{symbol} <span class="badge" style="background:{badge_bg};">{action}</span></h2><small>Source: Binance Auto-Scanner</small></div>
            <div style="text-align:right;"><div style="font-weight:bold; color:{theme_color};">CONFLUENCE: STRONG</div><small>Bias: {bias}</small></div>
        </div>
        <div class="output-body">
            <h4 style="color: {theme_color}; margin-bottom: 10px;">⚡ TRADE PLAN (1:2 R:R)</h4>
            <div class="grid-info">
                <div class="info-box"><div class="info-label">Entry</div><div class="info-value">{data.get('entry')}</div></div>
                <div class="info-box" style="border: 1px solid #ef4444;"><div class="info-label">Stop Loss</div><div class="info-value" style="color: #ef4444;">{data.get('sl')}</div></div>
                <div class="info-box" style="border: 1px solid #10b981;"><div class="info-label">Targets</div><div class="info-value" style="color: #10b981;">{tp_display}</div></div>
            </div>
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:20px; margin-bottom: 20px;">
                <div class="analysis-section"><div class="analysis-title">📊 Analisa Teknikal</div><p style="font-size:0.9rem; margin-top:5px;">{data.get('teknikal')}</p><p style="font-size:0.9rem;"><strong>Chart Pattern:</strong> {data.get('chart_pattern')}</p><p style="font-size:0.9rem;"><strong>Candle Pattern:</strong> {data.get('candle_pattern')}</p></div>
                <div class="analysis-section"><div class="analysis-title">🌍 Fundamental (Kontekstual)</div><p style="font-size:0.9rem; margin-top:5px;">{data.get('fundamental')}</p></div>
            </div>
            <div class="verdict-box" style="border-color: {theme_color};"><strong>🤖 Kesimpulan AI:</strong> "{data.get('alasan')}"</div>
        </div>
    </div>
    """
    return html

# --- MAIN APP LOGIC ---
st.title("AltaQuant: Institutional Engine")
tab1, tab2 = st.tabs(["🚀 ANALISA", "📜 HISTORY"])

# === TAB 1: DASHBOARD & SCANNER ===
with tab1:
    if 'results' not in st.session_state: st.session_state['results'] = []
    
    with st.sidebar:
        st.header("Kontrol")
        mode = st.radio("Mode", ["Manual Input", "Auto-Discovery"])
        sym_in = st.text_input("Simbol", "BTC/USDT").upper() if mode == "Manual Input" else None
        btn = st.button("MULAI ANALISA", type="primary")

    if not st.session_state['results'] and not btn:
        ov = get_market_overview()
        st.info("Pastikan VPN AKTIF. Sistem terhubung ke Binance Futures.")
        c1, c2 = st.columns(2)
        with c1: st.markdown(f'<div class="hero-metric"><div class="metric-lbl">BTC Price</div><div class="metric-val">${ov["btc_price"]:.2f}</div></div>', unsafe_allow_html=True)
        with c2: st.markdown(f'<div class="hero-metric"><div class="metric-lbl">System</div><div class="metric-val" style="color:#10b981">READY</div></div>', unsafe_allow_html=True)

    if btn:
        st.session_state['results'] = []
        with st.status("🔄 Menghubungkan ke Binance...", expanded=True) as status:
            if mode == "Auto-Discovery":
                status.write("Memindai 50 Koin Teraktif (Likuiditas > $20M)...")
                targets = scan_dynamic_market()
                if not targets:
                    status.write("Pasar Konsolidasi. Mengambil Top Cap untuk referensi.")
                    targets = [
                        {'symbol': 'BTC/USDT', 'bias': 'NEUTRAL'},
                        {'symbol': 'ETH/USDT', 'bias': 'NEUTRAL'},
                        {'symbol': 'SOL/USDT', 'bias': 'NEUTRAL'}
                    ]
            else:
                targets = [{'symbol': sym_in, 'bias': 'MANUAL'}]
                
            res_temp = []
            prog = st.progress(0)
            
            for idx, t in enumerate(targets):
                sym = t['symbol']
                prog.progress((idx+1)*int(100/len(targets)))
                df, context = get_ai_context_indo(sym)
                
                if df is not None:
                    # UPDATE: Prompt "Senior Trader" dengan Data 150 Candle
                    prompt = f"""
                    Role: Senior Crypto Trader (10yr Exp, Technical Analyst).
                    Task: Analisa {sym}. Bias Awal Sistem: {t['bias']}.
                    Data Lengkap: {context}
                    
                    INSTRUKSI KHUSUS CHART PATTERN (DATA 150 CANDLE):
                    1. Anda diberikan data mentah OHLC untuk 150 candle terakhir.
                    2. Gunakan "Mata Batin" AI Anda untuk mendeteksi pola grafik besar seperti:
                       - Head & Shoulders / Inverse H&S
                       - Double Top / Bottom
                       - Bull / Bear Flag
                       - Rising / Falling Wedge
                       - Triangle (Ascending/Descending)
                    3. Jika tidak ada pola textbook, jelaskan Struktur Pasar (Higher Highs / Lower Lows).
                    4. JANGAN PERNAH MENJAWAB "Tidak ada pola". Selalu ada struktur harga.
                    
                    INSTRUKSI LAIN:
                    - Fundamental: Jelaskan utilitas koin & sentimen naratif (AI/Meme/L1) saat ini.
                    - Candle Pattern: Gunakan hasil deteksi Python di data context.
                    - Plan: Wajib ada TP1 dan TP2 (Risk Reward 1:2 minimal).
                    
                    OUTPUT WAJIB JSON (Bahasa Indonesia):
                    {{
                        "fundamental": "...", 
                        "teknikal": "...", 
                        "chart_pattern": "...", 
                        "candle_pattern": "...", 
                        "keputusan": "LONG/SHORT", 
                        "entry": "...", 
                        "sl": "...", 
                        "tp1": "...", 
                        "tp2": "...", 
                        "alasan": "..."
                    }}
                    """
                    
                    # Request ke Gemini
                    raw = get_gemini_analysis(prompt)
                    
                    # Parsing dan Simpan
                    parsed_data = parse_indo_json(raw)
                    res_temp.append({'symbol': sym, 'data': parsed_data, 'df': df, 'bias': t['bias']})
            
            # Update Session State setelah Loop Selesai
            st.session_state['results'] = res_temp
            prog.empty()
            status.update(label="Analisa Selesai!", state="complete")

    # 3. RENDER HASIL (BAGIAN TAMPILAN)
    for res in st.session_state['results']:
        sym = res['symbol']
        
        # Tampilkan Grafik
        st.plotly_chart(plot_tv_chart(res['df'], sym), use_container_width=True)
        
        # Tampilkan Kartu Analisa HTML
        st.markdown(render_altaquant_card(sym, res['data'], res['bias']), unsafe_allow_html=True)
        
        # Tombol Simpan
        if st.button(f"💾 Simpan {sym} ke Jurnal", key=f"s_{sym}"):
            save_trade(sym, res['data'])
            st.success(f"Analisa {sym} tersimpan di Database untuk pembelajaran!")
        
        st.divider()

# === TAB 2: HISTORY & LEARNING ===
with tab2:
    st.header("📜 Jurnal Trading & Pembelajaran AI")
    st.info("Tandai WIN/LOSS untuk melatih sistem.")
    
    history = get_history()
    
    if not history:
        st.warning("Belum ada history. Lakukan analisa lalu simpan.")
    
    for row in history:
        with st.container():
            st.markdown(f'<div class="hist-card">', unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns([1.5, 4, 1.5, 2])
            
            with c1:
                color = "#10b981" if "LONG" in row['action'] else "#ef4444"
                st.markdown(f"<h3 style='margin:0; color:white;'>{row['symbol']}</h3>", unsafe_allow_html=True)
                st.markdown(f"<span style='background:{color}; padding:2px 8px; border-radius:4px; font-size:0.8em; color:white;'>{row['action']}</span>", unsafe_allow_html=True)
                st.caption(f"{row['timestamp'][:16]}")
                
            with c2:
                st.markdown(f"**Alasan:** {row['reason']}")
                tp_val = row['tp']
                st.markdown(f"<div style='font-size:0.8em; color:#cbd5e1;'>Entry: <b>{row['entry']}</b> | SL: <span style='color:#ef4444'>{row['sl']}</span> | TP: <span style='color:#10b981'>{tp_val}</span></div>", unsafe_allow_html=True)
                
                if row['outcome_note']:
                    st.markdown(f"<div style='margin-top:5px; padding:5px; background:#334155; border-radius:4px; font-size:0.8em;'>📝 <b>Note:</b> {row['outcome_note']}</div>", unsafe_allow_html=True)
            
            with c3:
                status = row['status']
                if status == 'WIN': st.markdown("<h3 style='color:#10b981; margin:0;'>WIN ✅</h3>", unsafe_allow_html=True)
                elif status == 'LOSS': st.markdown("<h3 style='color:#ef4444; margin:0;'>LOSS ❌</h3>", unsafe_allow_html=True)
                else: st.markdown("<h3 style='color:#facc15; margin:0;'>OPEN ⏳</h3>", unsafe_allow_html=True)
                
            with c4:
                if row['status'] == 'OPEN':
                    c_win, c_loss = st.columns(2)
                    with c_win:
                        if st.button("WIN", key=f"btn_win_{row['id']}"):
                            update_outcome_and_learn(row['id'], 'WIN', "Sesuai Analisa")
                            st.success("Nice Trade!")
                            time.sleep(0.5)
                            st.rerun()
                    with c_loss:
                        if st.button("LOSS", key=f"btn_loss_{row['id']}"):
                            st.session_state[f"loss_mode_{row['id']}"] = True
                    
                    if st.session_state.get(f"loss_mode_{row['id']}"):
                        with st.form(key=f"form_loss_{row['id']}"):
                            reason_loss = st.text_input("Kenapa Loss?", placeholder="Misal: Kena News")
                            if st.form_submit_button("Simpan"):
                                update_outcome_and_learn(row['id'], 'LOSS', reason_loss)
                                st.session_state[f"loss_mode_{row['id']}"] = False
                                st.rerun()
                                
            st.markdown('</div>', unsafe_allow_html=True)