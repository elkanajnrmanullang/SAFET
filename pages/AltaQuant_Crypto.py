import streamlit as st
import pandas as pd
import time

# =============================
# IMPORTS (PIPELINE INTEGRATION)
# =============================================================
from backend.crypto.pipeline import pipeline
from backend.crypto.data import get_top_symbols
from backend.crypto.screener import CryptoScreener
from backend.core.news import get_crypto_news

# =========================================================
#  NEWS CACHING WRAPPER
# =========================================================
@st.cache_data(ttl=300, show_spinner=False)
def get_cached_news(symbol):
    return get_crypto_news(symbol)

# =============================
# PAGE CONFIG
# =============================
st.set_page_config(
    page_title="AltaQuant Super Analyst",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================
# STYLING
# =============================
st.markdown("""
<style>
    .card-container {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
    }
    .header-pass { border-left: 5px solid #10b981; }
    .header-fail { border-left: 5px solid #ef4444; }
    .header-wait { border-left: 5px solid #f59e0b; }
    
    .sub-section { margin-top: 15px; border-top: 1px solid #334155; padding-top: 10px; }
    .sub-title { font-size: 0.9rem; font-weight: bold; color: #6366f1; margin-bottom: 8px; }
    
    .check-pass { color: #10b981; font-weight: bold; }
    .check-fail { color: #ef4444; font-weight: bold; }
    
    .logic-box { 
        background: #0f172a; 
        padding: 10px; 
        border-radius: 8px; 
        font-size: 0.8rem; 
        margin-bottom: 5px; 
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: flex-start;
        border: 1px solid #334155;
    }
    
    .logic-title { font-weight: bold; font-size: 0.9rem; margin-bottom: 4px; display: block; }
    .logic-desc { color: #94a3b8; font-size: 0.75rem; line-height: 1.3; }
    
    .summary-box {
        background-color: #0f172a;
        border: 1px dashed #475569;
        border-radius: 8px;
        padding: 15px;
        margin-top: 15px;
        font-size: 0.9rem;
        color: #e2e8f0;
        line-height: 1.6;
    }
    
    .strategy-tag {
        background-color: #312e81;
        color: #a5b4fc;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        border: 1px solid #4338ca;
        margin-left: 10px;
    }
</style>
""", unsafe_allow_html=True)

# =============================
# HELPER: RENDER CARD
# =============================
def render_analysis_card(symbol, screener_res, result_json=None):
    # Extract decision dari structure JSON Unifier
    # FIX: Menggunakan 'or {}' untuk mencegah NoneType error
    decision = result_json.get("final_decision", {}) if result_json else {} 
    technical_ctx = result_json.get("technical_signal", {}) if result_json else {}
    
    # Tentukan Status Header & Warna
    status_code = decision.get("status", "ANALYZING")
    strategy_name = decision.get("strategy", "None")
    
    status_color = "header-wait"
    icon = "⏳"
    main_status = f"WAITING ({status_code})"

    if screener_res["status"] == "FAIL":
        status_color = "header-fail"
        main_status = "REJECTED (SCREENING)"
        icon = "⛔"
    elif status_code == "EXECUTE":
        status_color = "header-pass"
        main_status = "EXECUTE SIGNAL"
        icon = "💎"
    elif status_code == "WAIT_FOR_TRIGGER":
        status_color = "header-wait"
        main_status = "WATCHLIST (NEAR ENTRY)"
        icon = "👀"
    elif status_code == "NO_TRADE" or status_code == "BLOCKED_BY_FUNDAMENTAL" or status_code == "EVENT_BLACKOUT":
        status_color = "header-fail"
        main_status = "NO TRADE / BLOCKED"
        icon = "🛑"

    # 1. BUKA CONTAINER (Start HTML Div)
    st.markdown(f"""
    <div class="card-container {status_color}">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div style="display:flex; align-items:center;">
                <h2 style="margin:0; color: #f8fafc;">{icon} {symbol}</h2>
                {f'<span class="strategy-tag">{strategy_name}</span>' if strategy_name != "None" else ''}
            </div>
            <h3 style="margin:0; color: #cbd5e1;">{main_status}</h3>
        </div>
    """, unsafe_allow_html=True)

    # 2. SCREENING SECTION
    st.markdown('<div class="sub-section"><div class="sub-title">TAHAP 0 — SCREENING RULES</div>', unsafe_allow_html=True)
    s_cols = st.columns(4)
    details = screener_res["details"]
    def c(val): return "check-pass" if "PASS" in val else "check-fail"

    s_cols[0].markdown(f"**Volume:** <br><span class='{c(details.get('Volume',''))}'>{details.get('Volume','-')}</span>", unsafe_allow_html=True)
    s_cols[1].markdown(f"**Volatility:** <br><span class='{c(details.get('Volatility',''))}'>{details.get('Volatility','-')}</span>", unsafe_allow_html=True)
    s_cols[2].markdown(f"**Structure:** <br><span class='{c(details.get('Structure',''))}'>{details.get('Structure','-')}</span>", unsafe_allow_html=True)
    s_cols[3].markdown(f"**Trend Pot:** <br><span class='{c(details.get('Trend_Potential',''))}'>{details.get('Trend_Potential','-')}</span>", unsafe_allow_html=True)
    
    if screener_res["status"] == "FAIL":
        reasons = ", ".join(screener_res.get("reasons", []))
        st.error(f"❌ **Reason:** {reasons}")
        st.markdown("</div>", unsafe_allow_html=True) # Tutup div jika fail
        return

    # 3. VISION AI SECTION (Jika ada hasil vision)
    vision = result_json.get("vision_analysis")
    if vision and vision.get("pattern"):
        st.markdown('<div class="sub-section"><div class="sub-title">👁️ VISION AI CONTEXT</div>', unsafe_allow_html=True)
        pat = vision.get('pattern')
        sent = vision.get('sentiment')
        conf = vision.get('confidence', 0)
        st.info(f"**Detected:** {pat} ({sent}) • Confidence: {conf:.0%}")

    # 4. WATERFALL ANALYSIS (3-TIER MATRIX DISPLAY)
    if decision:
        st.markdown('<div class="sub-section"><div class="sub-title">TAHAP 1 — STRATEGY MATRIX (WATERFALL)</div>', unsafe_allow_html=True)
        
        # Fundamental Guard
        fund = decision.get("fundamental", {})
        fund_flag = fund.get("flag", "GREEN")
        f_color = "check-fail" if fund_flag == "RED" else ("check-pass" if fund_flag == "GREEN" else "check-wait")
        st.markdown(f"**Fundamental Guard:** <span class='{f_color}'>{fund_flag}</span> <span style='font-size:0.8em'>({fund.get('reason', ['-'])[0]})</span>", unsafe_allow_html=True)
        
        col_h4, col_h1, col_m30, col_m15 = st.columns(4)
        
        # A. H4 (Anchor)
        h4_valid = technical_ctx.get('valid')
        h4_dir = technical_ctx.get('direction', 'NEUTRAL')
        h4_exhaustion = technical_ctx.get('exhaustion', False)
        h4_color = "#10b981" if h4_valid else "#ef4444"
        
        h4_desc_status = "Valid Structure & EMA"
        if h4_exhaustion: h4_desc_status += " | ⚠️ Exhaustion (Divergence)"
        if not h4_valid: h4_desc_status = "Invalid/Sideways"

        col_h4.markdown(f"""
        <div class="logic-box" style="border-left: 4px solid {h4_color};">
            <span class="logic-title">TF H4 (Anchor)</span>
            <span style="color: {h4_color}; font-weight:bold;">{h4_dir}</span>
            <span class="logic-desc">{h4_desc_status}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # B. H1 (Bias) - Diperbarui untuk Volatility Gate
        h1_volatility = result_json.get("bias_h1", {}).get("volatility", "NO_DATA")
        h1_msg = decision.get("reason", "")
        h1_ok = "H1" not in h1_msg and "Gatekeeper" not in h1_msg and h1_volatility != "LESU"
        
        # Warna H1 berdasarkan Volatility
        if h1_volatility == "OVERHEAT": h1_color = "#f59e0b" # Orange
        elif h1_volatility == "NORMAL": h1_color = "#10b981" # Green
        elif h1_volatility == "LESU": h1_color = "#ef4444" # Red (sudah diblok di Gatekeeper)
        else: h1_color = "#64748b"
        
        h1_desc_status = f"{'ALIGNED' if h1_ok else 'CONFLICT'} ({h1_volatility})"

        col_h1.markdown(f"""
        <div class="logic-box" style="border-left: 4px solid {h1_color};">
            <span class="logic-title">TF H1 (Bias)</span>
            <span style="color: {h1_color}; font-weight:bold;">{h1_desc_status}</span>
            <span class="logic-desc">Price vs EMA50 & Volatility Gate</span>
        </div>
        """, unsafe_allow_html=True)

        # C. M30 (Setup) - DINAMIS SESUAI STRATEGI
        notes = decision.get("notes", [])
        m30_note = next((n for n in notes if "M30" in n), "-")
        
        # Default State
        m30_status = "WAITING"
        m30_desc = "Scanning Zone..."
        m30_color = "#64748b"

        # Logic Matrix
        if "Tier 2" in strategy_name:
            m30_status = "BYPASSED 🚀"
            m30_desc = "Super Trend (ADX > 35)"
            m30_color = "#f59e0b" # Orange Warning
        elif "Tier 3" in strategy_name:
            m30_status = "SKIPPED 🛡️"
            m30_desc = "Local Reaction Only"
            m30_color = "#64748b" # Grey
        elif "Tier 1" in strategy_name and "Volatility Gated" in strategy_name:
             m30_status = "READY ✅"
             m30_desc = m30_note.replace("M30: ", "") + " (Tier 1 Forced)"
             m30_color = "#f59e0b"
        elif "Tier 1" in strategy_name:
            m30_status = "READY ✅"
            m30_desc = m30_note.replace("M30: ", "")
            m30_color = "#10b981"
        elif decision.get("status") == "WAIT_FOR_SETUP":
             m30_status = "NO SETUP"
             m30_desc = "No Zone / Sweep"
             m30_color = "#ef4444"

        col_m30.markdown(f"""
        <div class="logic-box" style="border-left: 4px solid {m30_color};">
            <span class="logic-title">TF M30 (Setup)</span>
            <span style="color: {m30_color}; font-weight:bold;">{m30_status}</span>
            <span class="logic-desc">{m30_desc}</span>
        </div>
        """, unsafe_allow_html=True)

        # D. M15 (Trigger)
        m15_note = next((n for n in notes if "M15" in n), "-")
        m15_color = "#64748b"
        m15_status = "LOCKED"

        if decision.get("status") == "WAIT_FOR_TRIGGER":
            m15_status = "WAIT TRIGGER"
            m15_color = "#f59e0b"
        elif decision.get("status") == "EXECUTE":
            m15_status = "FIRED 🔥"
            m15_color = "#10b981"
        
        m15_desc = m15_note.replace("M15: ", "") if m15_note != "-" else "Breakout / Bounce"

        col_m15.markdown(f"""
        <div class="logic-box" style="border-left: 4px solid {m15_color};">
            <span class="logic-title">TF M15 (Exec)</span>
            <span style="color: {m15_color}; font-weight:bold;">{m15_status}</span>
            <span class="logic-desc">{m15_desc}</span>
        </div>
        """, unsafe_allow_html=True)

        # AI Verdict
        verdict_text = result_json.get("explainability", "Generating analysis...")
        
        st.markdown(f"""
        <div class="summary-box">
            <strong style="color: #6366f1;">📝 AI ANALYST (Executive Summary)</strong><br>
            {verdict_text}
        </div>
        """, unsafe_allow_html=True)

        # Execution Plan
        if decision.get("status") == "EXECUTE":
            st.markdown('<div class="sub-section"><div class="sub-title">🎯 EXECUTION PLAN (Fixed RR 1:2)</div>', unsafe_allow_html=True)
            risk = result_json.get("risk", {})
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("Action", decision.get("direction"))
            r2.metric("Entry", f"${risk.get('entry', 0):,.4f}")
            r3.metric("Stop Loss", f"${risk.get('stop_loss', 0):,.4f}")
            r4.metric("Take Profit", f"${risk.get('take_profit', 0):,.4f}")
            
            # Tampilkan Risk Note (terutama jika ada Scaling Tier 3 atau Exhaustion)
            risk_note = risk.get('note', '')
            st.success(f"Position Size: {risk.get('position_size')} Units | Risk: ${risk.get('risk_amount')} ({risk_note})")

    # 5. TUTUP CONTAINER (Close HTML Div)
    st.markdown("</div>", unsafe_allow_html=True) 

# =============================
# MAIN APP LOGIC
# =============================
st.title("AltaQuant • Institutional Grade DSS")
st.markdown("Automated Screening & 3-Layer Strategy Matrix")

screener = CryptoScreener()

with st.sidebar:
    st.title("🛡️ AltaQuant Control")
    mode = st.radio("Mode Operasi", ["Auto-Scanner (Hunter)", "Single Analyzer"])
    
    if mode == "Single Analyzer":
        symbol = st.text_input("Symbol", "BTC/USDT").upper()
        
        st.markdown("---")
        st.write("📸 **Vision Context (Opsional)**")
        st.caption("Upload gambar chart untuk validasi pola H4.")
        uploaded_file = st.file_uploader("Upload Chart Image", type=["jpg", "png", "jpeg"])
        
        run_btn = st.button("🚀 START ANALYSIS", type="primary")
    else:
        st.info("Scanner akan memindai Top 50 Volume Koin. Otomatis mencari Setup EXECUTE dan WATCHLIST.")
        scan_limit = st.slider("Jumlah Koin Di-scan", 10, 50, 20)
        run_scan = st.button("🔍 START AUTO-SCANNER", type="primary")

# ----------------------------------------
# MODE 1: MARKET SCANNER (AUTO-HUNTER)
# ----------------------------------------
if mode == "Auto-Scanner (Hunter)":
    if run_scan:
        st.header("🔍 Auto-Scanner Results")
        
        log_placeholder = st.empty()
        logs = []

        def add_log(msg):
            logs.insert(0, f"> {msg}")
            log_text = "\n".join(logs[:8])
            log_placeholder.markdown(f"```bash\n{log_text}\n```")

        symbols = []
        st.write("Mencoba menghubungi Server Binance...")
        
        with st.spinner("📡 Handshaking with Exchange (Check VPN)..."):
            try:
                symbols = get_top_symbols(limit=scan_limit)
            except Exception as e:
                add_log(f"Connection Fatal Error: {e}")

        if not symbols:
            st.error("❌ **KONEKSI GAGAL!**")
            st.stop()

        # CONTAINER UNTUK HASIL
        diamonds_container = st.container()
        watchlist_container = st.container()
        
        with diamonds_container:
            st.markdown("### 💎 DIAMONDS (Ready to Execute)")
            st.caption("Setup yang lolos salah satu dari 3 Tier Strategy.")
            
        with watchlist_container:
            st.markdown("### 👀 WATCHLIST (Near Entry)")
            st.caption("Setup valid yang menunggu trigger M15.")

        found_diamonds = []
        found_watchlist = []

        with st.status("🚀 Scanning Market...", expanded=True) as status:
            add_log(f"Connection Success. Scanning Top {len(symbols)} coins.")
            
            progress_bar = st.progress(0)
            
            for i, sym in enumerate(symbols):
                # Update progress
                progress_bar.progress((i + 1) / len(symbols))
                status.update(label=f"Scanning {sym} ({i+1}/{len(symbols)})...")
                
                # Screening Tahap 0
                try:
                    screen_res = screener.run_screen(sym)
                except Exception as e:
                    continue

                if screen_res.get("status") == "FAIL":
                    add_log(f"   [X] {sym}: REJECTED (Screening)")
                    continue 
                
                add_log(f"   [!] {sym}: PASSED SCREEN. Running Pipeline...")
                
                # Jalankan Pipeline Utama (Tanpa Gambar)
                result_json = pipeline.run(sym)
                
                # FIX: Mencegah AttributeError jika 'final_decision' bernilai None
                decision = result_json.get("final_decision") or {}
                
                status_code = decision.get("status")
                
                # KATEGORISASI HASIL
                if status_code == "EXECUTE":
                    strategy = decision.get("strategy", "Unknown")
                    add_log(f"   💎 {sym}: EXECUTE! ({strategy})")
                    found_diamonds.append({
                        "symbol": sym, "screen": screen_res, "result": result_json
                    })
                elif status_code == "WAIT_FOR_TRIGGER":
                    add_log(f"   👀 {sym}: WATCHLIST (Wait M15 Trigger)")
                    found_watchlist.append({
                        "symbol": sym, "screen": screen_res, "result": result_json
                    })
                else:
                    add_code = status_code if status_code else "Pipeline Error"
                    add_log(f"   [O] {sym}: {add_code}")
                    
            progress_bar.empty()
            status.update(label="✅ Auto-Scan Complete", state="complete")
            
        # RENDER HASIL DI CONTAINER TERPISAH
        
        with diamonds_container:
            if not found_diamonds:
                st.info("Belum ada setup EXECUTE saat ini.")
            for cand in found_diamonds:
                render_analysis_card(cand['symbol'], cand['screen'], cand['result'])
        
        with watchlist_container:
            st.markdown("---")
            if not found_watchlist:
                st.info("Tidak ada setup Near Entry.")
            for cand in found_watchlist:
                render_analysis_card(cand['symbol'], cand['screen'], cand['result'])

# ----------------------------------------
# MODE 2: SINGLE ANALYZER
# ----------------------------------------
elif mode == "Single Analyzer":
    if run_btn:
        st.header(f"Deep Analysis: {symbol}")
        
        with st.spinner("🤖 Vision AI & Pipeline sedang bekerja..."):
            
            news = get_cached_news(symbol)
            screen_res = screener.run_screen(symbol)
            
            result_json = None
            
            if screen_res["status"] == "PASS":
                image_bytes = uploaded_file.getvalue() if uploaded_file else None
                result_json = pipeline.run(symbol, user_image_bytes=image_bytes)
            
            render_analysis_card(symbol, screen_res, result_json)
            
            with st.expander("📄 Read News Context", expanded=False):
                st.info(news)