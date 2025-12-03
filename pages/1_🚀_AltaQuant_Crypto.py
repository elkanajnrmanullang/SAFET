import streamlit as st
import plotly.graph_objects as go
import json
import re
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

    .tech-section { background: rgba(0,0,0,0.2); padding: 15px; border-radius: 8px; margin-bottom: 15px; border: 1px solid rgba(255,255,255,0.05); }
    .tech-title { color: var(--text-muted); font-size: 0.85rem; font-weight: bold; border-bottom: 1px solid var(--border); padding-bottom: 8px; margin-bottom: 10px; }
    .tech-item { margin-bottom: 8px; font-size: 0.95rem; }
    .tech-number { color: var(--primary); font-weight: bold; margin-right: 5px; }
    
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

    html = f"""
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
        <div class="tech-section">
            <div class="tech-title">FUNDAMENTAL</div>
            <p style="color:#e2e8f0; font-size:0.95rem; margin:0;">{data.get('fundamental', '-')}</p>
        </div>
        <div class="tech-section">
            <div class="tech-title">TEKNIKAL BREAKDOWN</div>
            <div class="tech-item"><span class="tech-number">1. Indikator:</span> {data.get('tek_indikator', '-')}</div>
            <div class="tech-item"><span class="tech-number">2. Candle Pattern:</span> {data.get('tek_candle', '-')}</div>
            <div class="tech-item"><span class="tech-number">3. Chart Pattern:</span> {data.get('tek_chart', '-')}</div>
            <div class="tech-item"><span class="tech-number">4. Teknikal Lainnya:</span> {data.get('tek_lain', '-')}</div>
        </div>
        <div class="verdict-box" style="border-color: {verdict_color};">
            <strong>🤖 SUMMARY (AI Verdict):</strong> "{summary}"
        </div>
    </div>
</div>
"""
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
                if not targets:
                    status.warning("⚠️ Scanner tidak menemukan data. Menggunakan Default: BTC/ETH.")
                    targets = [{'symbol': 'BTC/USDT', 'bias': 'NEUTRAL'}, {'symbol': 'ETH/USDT', 'bias': 'NEUTRAL'}]

            res_temp = []
            
            for t in targets:
                sym = t['symbol']
                status.write(f"🔍 Menganalisa {sym} ({analysis_mode})...")
                
                df, context, poc = get_ai_context_indo(sym)
                
                if df is not None:
                    # --- PROMPT STRATEGY V4.3 (ALTAQUANT PROTOCOL) ---
                    if analysis_mode == "Futures (Scalping)":
                        strategy_prompt = """
                        MODE: FUTURES (SCALPING/INTRADAY) - ALTAQUANT V4.3 PROTOCOL
                        
                        [INSTRUKSI UTAMA]:
                        Tugasmu adalah menganalisa pasar dengan "Rule of Two" (Keseimbangan Indikator).
                        JANGAN GUNAKAN SKOR PERSENTASE. Gunakan logika Valid/Invalid dengan penjelasan detail.
                        
                        1. INDIKATOR & TREND (VALID KARENA...):
                           - Wajib jelaskan Validitas masing-masing indikator.
                           - Contoh: "RSI: Valid (KARENA terjadi divergence positif di area oversold)."
                           - Contoh: "Volume: Invalid (KARENA tidak ada spike signifikan)."
                           - Cek Rule of Two: Minimal 2 indikator keluarga berbeda valid?
                           
                        2. CANDLE PATTERN (ISOLATED & CONFIRMED LOGIC):
                           - Pola candle adalah KONFIRMASI TAMBAHAN.
                           - Cek di data OHLC Terakhir: Jika pola terjadi pada candle terakhir (Closing), perhatikan apakah arahnya mendukung Trend.
                           - Aturan Konfirmasi: Jika pola Reversal muncul tapi candle selanjutnya (di masa depan) belum ada, tandai sebagai "Menunggu Konfirmasi".
                           - Jangan biarkan pola candle membatalkan sinyal Trend/Indikator yang kuat.
                           
                        3. CHART PATTERN (HYBRID):
                           - Prioritaskan hasil Vision AI. Jika Vision AI "Tidak Terdeteksi", gunakan hasil Math Fallback.
                           
                        4. KEPUTUSAN FINAL:
                           - Jika Trend Valid + minimal 1 Indikator Momentum Valid -> LONG/SHORT.
                           - Jika Indikator bertentangan (50:50) -> WAIT.
                        
                        [RISK MANAGEMENT]:
                        - SL Wajib Struktural.
                        - TP Minimal 1:2.
                        """
                    else:
                        strategy_prompt = """
                        MODE: SPOT (LONG TERM ACCUMULATION)
                        Strategi: Buy on Weakness.
                        Trigger: Harga menyentuh MA 99 Daily atau RSI Weekly Oversold.
                        Action: Dollar Cost Averaging (DCA).
                        """

                    prompt = f"""
                    Role: AltaQuant Decision Engine.
                    Task: Analisa Kripto {sym}.
                    Context Data: {context}
                    
                    {strategy_prompt}
                    
                    CRITICAL INSTRUCTION:
                    - Keluaran WAJIB format JSON murni (Plain Text).
                    - DILARANG menggunakan Markdown/HTML dalam value JSON.
                    - Pada bagian 'tek_indikator' dan 'tek_candle', WAJIB sertakan alasan (Valid/Invalid KARENA...).
                    
                    OUTPUT FORMAT (STRICT JSON):
                    {{
                        "fundamental": "Analisa fundamental singkat...",
                        "tek_indikator": "Detail Validitas Indikator (RSI, MA, Vol)...",
                        "tek_candle": "Detail Validitas Candle (Confirmed/Unconfirmed)...",
                        "tek_chart": "Detail Validitas Chart Pattern...",
                        "tek_lain": "Fibs, Support/Resist...",
                        "summary": "Kesimpulan Naratif AI...",
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
        html_card = render_output_card(sym, res['data'], res['mode'])
        st.markdown(html_card, unsafe_allow_html=True)
        
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
        
        if 'feedback_mode' not in st.session_state:
            st.session_state['feedback_mode'] = {}

        for row in history:
            trade_id = row['id']
            with st.expander(f"{row['symbol']} - {row['action']} ({row['status']})"):
                st.write(f"**Reason:** {row['reason']}")
                st.write(f"**Setup:** Entry {row['entry']} | SL {row['sl']} | TP {row['tp']}")
                st.caption(f"Time: {row['timestamp']}")
                
                if row['status'] == 'OPEN':
                    st.markdown("---")
                    
                    current_feedback = st.session_state['feedback_mode'].get(trade_id)
                    
                    if current_feedback is None:
                        c1, c2 = st.columns(2)
                        if c1.button("✅ WIN", key=f"btn_w_{trade_id}"):
                            st.session_state['feedback_mode'][trade_id] = 'WIN'
                            st.rerun()
                        
                        if c2.button("❌ LOSS", key=f"btn_l_{trade_id}"):
                            st.session_state['feedback_mode'][trade_id] = 'LOSS'
                            st.rerun()
                            
                    else:
                        feedback_type = current_feedback
                        st.info(f"Adding Feedback for: {feedback_type}")
                        
                        note_input = st.text_input(
                            f"Apa penyebab {feedback_type}?", 
                            "Setup Sesuai Analisa" if feedback_type == 'WIN' else "Kena SL / Invalidasi",
                            key=f"input_{trade_id}"
                        )
                        
                        c_confirm, c_cancel = st.columns([1, 1])
                        
                        if c_confirm.button(f"Confirm {feedback_type}", type="primary", key=f"conf_{trade_id}"):
                            update_outcome_and_learn(trade_id, feedback_type, note_input)
                            del st.session_state['feedback_mode'][trade_id]
                            st.success("Learning Saved!")
                            st.rerun()
                            
                        if c_cancel.button("Cancel", key=f"canc_{trade_id}"):
                            del st.session_state['feedback_mode'][trade_id]
                            st.rerun()