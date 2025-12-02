import streamlit as st
import plotly.graph_objects as go
import json
import re
import textwrap  # <--- SOLUSI INTI: Untuk membersihkan indentasi HTML
from backend.crypto_data import get_ai_context_indo, scan_dynamic_market, get_market_overview
from backend.ai_engine import get_gemini_analysis
from backend.database import save_trade, get_history, update_outcome_and_learn, get_performance_stats

st.set_page_config(page_title="AltaQuant Pro", layout="wide", page_icon="🚀")

# --- CSS STYLING (HTML DESIGN v3.3) ---
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
        --text-muted: #94a3b8;
        --border: #334155;
        --futures-color: #f43f5e;
        --spot-color: #34d399;
    }

    .output-container {
        border: 1px solid var(--border);
        border-radius: 12px;
        overflow: hidden;
        margin-bottom: 20px;
        background: var(--bg-card);
    }
    
    .card-header {
        padding: 15px 25px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid;
    }
    
    .futures-header { background: linear-gradient(90deg, rgba(244, 63, 94, 0.2), transparent); border-bottom-color: var(--futures-color); }
    .spot-header { background: linear-gradient(90deg, rgba(52, 211, 153, 0.2), transparent); border-bottom-color: var(--spot-color); }

    .card-body { padding: 25px; }

    .grid-info { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 20px; }
    
    .info-box { background: rgba(0, 0, 0, 0.3); padding: 15px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05); }
    .info-label { font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; margin-bottom: 5px; font-weight: 600; }
    .info-value { font-size: 1.1rem; font-weight: bold; color: white; }

    .verdict-box { background: rgba(15, 23, 42, 0.6); border-left: 4px solid; padding: 15px; margin-top: 15px; font-style: italic; color: #e2e8f0; }

    .tech-list { list-style: none; padding-left: 0; }
    .tech-list li { margin-bottom: 8px; color: #cbd5e1; }
    .tech-label { color: var(--primary); font-weight: bold; margin-right: 5px; }
    
    .metric-box { text-align: center; background: var(--bg-card); padding: 10px; border-radius: 8px; border: 1px solid var(--border); margin-bottom: 10px; }
    .metric-val { font-size: 1.5rem; font-weight: bold; color: white; }
    .metric-lbl { font-size: 0.8rem; color: var(--text-muted); }
</style>
""", unsafe_allow_html=True)

# --- FUNGSI PARSING & CLEANING ---
def clean_html_tags(text):
    """Menghapus tag HTML jika AI nakal memasukkannya"""
    clean = re.sub(r'<[^>]*>', '', str(text))
    return clean

def parse_indo_json(text):
    try:
        # Hapus markdown code block
        clean = re.sub(r'```json\s*|\s*```', '', text).strip()
        clean = clean.replace('json\n', '')
        
        data = json.loads(clean)
        
        # Bersihkan setiap value dari HTML tags
        for key, val in data.items():
            if isinstance(val, str):
                data[key] = clean_html_tags(val)
                
        return data
    except:
        return {
            "fundamental": "Gagal memuat fundamental.",
            "tek_indikator": "Data error.", "tek_chart": "-", "tek_candle": "-", "tek_lain": "-",
            "summary": clean_html_tags(text[:500]), "keputusan": "WAIT", "entry": "-", "sl": "-", "tp1": "-", "tp2": "-"
        }

def plot_tv_chart(df, symbol):
    if df is None: return None
    fig = go.Figure(data=[go.Candlestick(x=df['timestamp'], open=df['open'], high=df['high'], low=df['low'], close=df['close'])])
    fig.update_layout(height=400, template="plotly_dark", title=f"{symbol} (H1)", xaxis_rangeslider_visible=False, paper_bgcolor="#1e293b", plot_bgcolor="#0f172a")
    return fig

def render_output_card(sym, data, mode):
    action = data.get('keputusan', 'WAIT').upper()
    summary = data.get('summary', '-')
    
    if mode == "Futures (Scalping)":
        header_class = "futures-header"
        badge_bg = "var(--futures-color)"
        verdict_color = "#f43f5e"
        entry_box = data.get('entry')
        sl_box = f"<span style='color:var(--danger)'>{data.get('sl')}</span>"
        tp_box = f"<span style='color:var(--secondary)'>{data.get('tp1')} | {data.get('tp2')}</span>"
    else:
        header_class = "spot-header"
        badge_bg = "var(--spot-color)"
        verdict_color = "#34d399"
        entry_box = "DCA / Accumulate"
        sl_box = "Invalidation: Candle Close < Support"
        tp_box = "Long Term Hold"

    # --- PERBAIKAN UTAMA: textwrap.dedent ---
    # Ini akan menghapus spasi indentasi di awal setiap baris string HTML
    # sehingga Markdown tidak menganggapnya sebagai Code Block.
    html = textwrap.dedent(f"""
    <div class="output-container">
        <div class="card-header {header_class}">
            <div>
                <h2 style="margin:0; font-size: 1.5rem; color:white !important;">{sym} 
                    <span style="background:{badge_bg}; color:{'white' if mode=='Futures (Scalping)' else 'black'}; padding:2px 10px; border-radius:4px; font-size:0.6em; vertical-align:middle;">{action}</span>
                </h2>
                <small style="color:#94a3b8;">Mode: {mode}</small>
            </div>
            <div style="text-align:right;">
                <div style="font-weight:bold; color:{badge_bg};">AI CONFIDENCE</div>
                <small style="color:#aaa;">Hybrid Logic Verified</small>
            </div>
        </div>
        
        <div class="card-body">
            <div class="grid-info">
                <div class="info-box">
                    <div class="info-label">Entry Zone</div>
                    <div class="info-value">{entry_box}</div>
                </div>
                <div class="info-box" style="border-color: rgba(239, 68, 68, 0.3);">
                    <div class="info-label">Stop Loss</div>
                    <div class="info-value">{sl_box}</div>
                </div>
                <div class="info-box" style="border-color: rgba(16, 185, 129, 0.3);">
                    <div class="info-label">Take Profit</div>
                    <div class="info-value">{tp_box}</div>
                </div>
            </div>

            <div style="margin-bottom:15px;">
                <h4 style="color:#94a3b8; border-bottom:1px solid #334155; padding-bottom:5px;">Fundamental & Sentiment</h4>
                <p style="color:#e2e8f0; font-size:0.95rem;">{data.get('fundamental', '-')}</p>
            </div>

            <div>
                <h4 style="color:#94a3b8; border-bottom:1px solid #334155; padding-bottom:5px;">Technical Breakdown</h4>
                <ul class="tech-list">
                    <li><span class="tech-label">Chart Pattern:</span> {data.get('tek_chart', '-')}</li>
                    <li><span class="tech-label">Candle Pattern:</span> {data.get('tek_candle', '-')}</li>
                    <li><span class="tech-label">Indicators:</span> {data.get('tek_indikator', '-')}</li>
                </ul>
            </div>
            
            <div class="verdict-box" style="border-color: {verdict_color};">
                <strong>🤖 AI Analysis:</strong> "{summary}"
            </div>
        </div>
    </div>
    """)
    return html

# --- SIDEBAR ---
with st.sidebar:
    st.header("🎛️ Control Center")
    analysis_mode = st.selectbox("Mode Analisa", ["Futures (Scalping)", "Spot (Investasi)"])
    mode_input = st.radio("Metode Input", ["Manual Input", "Auto-Discovery"])
    sym_in = st.text_input("Simbol Pair", "BTC/USDT").upper() if mode_input == "Manual Input" else None
    
    st.markdown("---")
    st.header("📊 Performance")
    stats = get_performance_stats()
    c1, c2 = st.columns(2)
    with c1: st.markdown(f'<div class="metric-box"><div class="metric-val">{stats["win_rate"]:.1f}%</div><div class="metric-lbl">Win Rate</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-box"><div class="metric-val">{stats["total"]}</div><div class="metric-lbl">Trades</div></div>', unsafe_allow_html=True)

# --- MAIN PAGE ---
st.title(f"AltaQuant: {analysis_mode}")

if 'results' not in st.session_state: st.session_state['results'] = []

if not st.session_state['results']:
    ov = get_market_overview()
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(f'<div class="metric-box"><div class="metric-lbl">BTC Price</div><div class="metric-val">${ov["btc_price"]:,.2f}</div></div>', unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="metric-box"><div class="metric-lbl">24h Change</div><div class="metric-val" style="color:{"#10b981" if ov["btc_change"]>0 else "#ef4444"}">{ov["btc_change"]:.2f}%</div></div>', unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="metric-box"><div class="metric-lbl">System</div><div class="metric-val" style="color:#10b981">ONLINE</div></div>', unsafe_allow_html=True)

tab1, tab2 = st.tabs(["⚡ ANALISA MARKET", "📜 TRADE HISTORY"])

with tab1:
    if st.button("MULAI ANALISA", type="primary"):
        st.session_state['btn_clicked'] = True
        with st.status("🧠 AltaQuant AI Working...", expanded=True) as status:
            
            if mode_input == "Manual Input":
                targets = [{'symbol': sym_in, 'bias': 'MANUAL'}]
            else:
                status.write("📡 Scanning Top 10 Volatile Assets & Filtering Top 5 Liquid...")
                targets = scan_dynamic_market()
                
                # JIKA SCANNER GAGAL, BERITAHU USER ALASANNYA
                if not targets:
                    status.warning("⚠️ Scanner tidak menemukan data. Menggunakan Default: BTC/ETH.")
                    targets = [{'symbol': 'BTC/USDT', 'bias': 'NEUTRAL'}, {'symbol': 'ETH/USDT', 'bias': 'NEUTRAL'}]

            res_temp = []
            
            for t in targets:
                sym = t['symbol']
                status.write(f"🔍 Menganalisa {sym} ({analysis_mode})...")
                
                df, context, poc = get_ai_context_indo(sym)
                
                if df is not None:
                    # PROMPT DESIGN v3.5 (No HTML in Output)
                    if analysis_mode == "Futures (Scalping)":
                        strategy_prompt = """
                        MODE: FUTURES (SCALPING/INTRADAY)
                        PHASE 1 (TREND FILTER): Gunakan EMA 200 H1. Jika Harga < EMA 200, bias BEARISH. Jika Harga > EMA 200, bias BULLISH.
                        PHASE 2 (STRICT ENTRY RULES): 
                        - HANYA ENTRY JIKA: Breakout/Breakdown Chart Pattern DENGAN Candle Confirmation (Hammer/Engulfing).
                        - ATAU: Bounce di Support/Resist/POC DENGAN Candle Confirmation.
                        - Validasi: Divergence RSI.
                        - JANGAN ENTRY jika harga di 'No Man's Land' (tengah-tengah).
                        PHASE 3 (RISK): Risk:Reward min 1:2. SL di titik invalidasi.
                        """
                    else:
                        strategy_prompt = """
                        MODE: SPOT (LONG TERM ACCUMULATION)
                        PHASE 1 (MACRO): Fokus Trend Weekly/Daily.
                        PHASE 2 (DISCOUNT): Entry saat RSI Oversold atau Support Kuat.
                        PHASE 3 (EXECUTION): Dollar Cost Average (DCA).
                        """

                    prompt = f"""
                    Role: AltaQuant Decision Engine.
                    Task: Analisa Kripto {sym}.
                    Context Data: {context}
                    
                    {strategy_prompt}
                    
                    CRITICAL INSTRUCTION:
                    - Keluaran WAJIB format JSON murni.
                    - VALUENYA HARUS TEKS BIASA (PLAIN TEXT).
                    - DILARANG KERAS menggunakan tag HTML (seperti <div>, <b>, <ul>) di dalam nilai JSON.
                    - DILARANG menggunakan Markdown (seperti **bold**) di dalam nilai JSON.
                    
                    OUTPUT FORMAT (STRICT JSON):
                    {{
                        "fundamental": "Analisa singkat (Plain Text)...",
                        "tek_indikator": "Status RSI/MACD/EMA (Plain Text)...",
                        "tek_chart": "Nama Pola Chart (Plain Text)...",
                        "tek_candle": "Nama Pola Candle (Plain Text)...",
                        "summary": "Kesimpulan Naratif AI (Plain Text)...",
                        "keputusan": "LONG/SHORT/WAIT",
                        "entry": "Angka/Range",
                        "sl": "Angka", 
                        "tp1": "Angka",
                        "tp2": "Angka",
                        "alasan": "Alasan singkat"
                    }}
                    """
                    
                    try:
                        raw = get_gemini_analysis(prompt)
                        parsed = parse_indo_json(raw)
                        res_temp.append({'symbol': sym, 'data': parsed, 'df': df, 'mode': analysis_mode})
                    except Exception as e:
                        st.error(f"Gagal analisa {sym}: {e}")
            
            st.session_state['results'] = res_temp
            status.update(label="Analisa Selesai!", state="complete")

    for res in st.session_state['results']:
        sym = res['symbol']
        st.plotly_chart(plot_tv_chart(res['df'], sym), use_container_width=True)
        # Gunakan unsafe_allow_html=True agar div/style dirender browser
        st.markdown(render_output_card(sym, res['data'], res['mode']), unsafe_allow_html=True)
        
        c_btn, _ = st.columns([1, 4])
        with c_btn:
            if st.button(f"💾 Simpan ke Database", key=f"s_{sym}"):
                save_trade(sym, res['data'])
                st.toast(f"Keputusan untuk {sym} disimpan!", icon="✅")
        st.divider()

with tab2:
    st.markdown("### 📜 Trade History & Adaptive Learning")
    history = get_history()
    
    if not history:
        st.info("Belum ada data history.")
    else:
        st.markdown("""
        <div style="display:grid; grid-template-columns: 1fr 1fr 2fr 1fr; background:#0f172a; padding:10px; font-weight:bold; border-bottom:1px solid #334155; margin-bottom:10px;">
            <div>Symbol</div><div>Action</div><div>Reason</div><div>Status</div>
        </div>
        """, unsafe_allow_html=True)
        
        for row in history:
            with st.expander(f"{row['symbol']} - {row['action']} ({row['status']})"):
                st.write(f"**Reason:** {row['reason']}")
                st.write(f"**Setup:** Entry {row['entry']} | SL {row['sl']} | TP {row['tp']}")
                st.caption(f"Time: {row['timestamp']}")
                
                if row['status'] == 'OPEN':
                    st.markdown("---")
                    c1, c2 = st.columns(2)
                    if c1.button("✅ WIN", key=f"w_{row['id']}"):
                        note = st.text_input("Feedback Positif:", "Setup Valid", key=f"nw_{row['id']}")
                        if st.button("Confirm Win", key=f"cw_{row['id']}"):
                            update_outcome_and_learn(row['id'], 'WIN', note)
                            st.rerun()
                    
                    if c2.button("❌ LOSS", key=f"l_{row['id']}"):
                        note = st.text_input("Feedback Negatif:", "Kena SL", key=f"nl_{row['id']}")
                        if st.button("Confirm Loss", key=f"cl_{row['id']}"):
                            update_outcome_and_learn(row['id'], 'LOSS', note)
                            st.rerun()