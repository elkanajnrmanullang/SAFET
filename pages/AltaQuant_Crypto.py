import streamlit as st
import pandas as pd
import time

# =============================
# IMPORTS (MODULAR STRUCTURE)
# =============================
from backend.crypto.data import build_ai_context, get_top_symbols
from backend.crypto.engine import final_decision
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
        padding: 12px; 
        border-radius: 8px; 
        font-size: 0.85rem; 
        margin-bottom: 5px; 
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: center;
        border: 1px solid #334155;
    }
    
    .logic-title { font-weight: bold; font-size: 0.95rem; margin-bottom: 4px; display: block; }
    .logic-desc { color: #94a3b8; font-size: 0.8rem; line-height: 1.3; }
    
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
</style>
""", unsafe_allow_html=True)

# =========================================================
#  HELPER: HUMAN NARRATIVE GENERATOR
# =========================================================
def generate_human_verdict(symbol, decision, tech_ctx):
    status = decision.get("status", "NO_TRADE")
    h4 = tech_ctx.get("trend_h4", {})
    h1 = tech_ctx.get("bias_h1", {})
    fund = decision.get("fundamental", {})
    
    narrative = ""
    recommendation = ""

    # KASUS 1: Masalah Trend Utama (H4)
    if not h4.get("valid"):
        adx = h4.get("adx", 0)
        narrative = f"Analisis terhenti. **Trend H4 Lemah/Sideways** (ADX {adx:.1f} < 20). Pasar sedang tidak memiliki arah yang jelas."
        recommendation = "⏳ **Saran:** Jangan entry. Risiko *choppy market* tinggi."

    # KASUS 2: Masalah Bias H1
    elif not h1.get("aligned"):
        trend_dir = h4.get("direction")
        narrative = f"Trend H4 **{trend_dir}**, tapi H1 bergerak berlawanan (Divergence). Harga sedang koreksi melawan arus utama."
        recommendation = f"⏳ **Saran:** Tunggu momentum H1 kembali searah dengan {trend_dir}."

    # KASUS 3: Masalah Fundamental
    elif fund.get("flag") == "RED":
        reason = fund.get("reason", ["Unknown"])[0]
        narrative = f"Teknikal bagus, tapi trade diblokir oleh **Fundamental Guard**. Isu: **{reason}**."
        recommendation = "⛔ **Saran:** Terlalu berisiko. Hindari trading saat bad news."

    # KASUS 4: Menunggu Trigger M15
    elif status == "WAIT_FOR_TRIGGER" or status == "NO_TRADE":
        direction = h4.get("direction")
        
        if direction == "SHORT":
            focus = "Fokus cari 'Rejection' di Resistance atau 'Breakdown' di Support."
        else:
            focus = "Fokus cari 'Bounce' di Support atau 'Breakout' di Resistance."

        narrative = f"H4 & H1 sudah **Compact ({direction})**. Sistem sedang memantau M15 untuk konfirmasi entry presisi."
        recommendation = f"👀 **Saran:** Masukkan Watchlist! {focus} Entry jika muncul volume tinggi."

    # KASUS 5: EXECUTE
    elif status == "EXECUTE":
        direction = decision.get("direction")
        detail = decision.get("notes")[-1] if decision.get("notes") else "Confirmed"
        narrative = f"**SETUP CONFIRMED!** Market struktur H4-H1-M15 selaras. Trigger M15 tervalidasi: **{detail}**."
        recommendation = "💎 **Saran:** EKSEKUSI SEKARANG. Gunakan SL/TP yang disarankan."

    else:
        narrative = f"Sistem memutuskan: {status}. Alasan: {decision.get('reason')}."
        recommendation = "Pantau terus perkembangan market."

    return f"{narrative}\n\n{recommendation}"

# =============================
# HELPER: RENDER CARD (UPDATED BOX LOGIC)
# =============================
def render_analysis_card(symbol, screener_res, decision=None, technical_ctx=None):
    if screener_res["status"] == "FAIL":
        status_color = "header-fail"
        main_status = "REJECTED (SCREENING)"
        icon = "⛔"
    elif decision and decision["status"] == "EXECUTE":
        status_color = "header-pass"
        main_status = "EXECUTE SIGNAL"
        icon = "💎"
    else:
        status_color = "header-wait"
        main_status = "WAIT / MONITOR"
        icon = "⏳"

    st.markdown(f"""
    <div class="card-container {status_color}">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <h2 style="margin:0; color: #f8fafc;">{icon} {symbol}</h2>
            <h3 style="margin:0; color: #cbd5e1;">{main_status}</h3>
        </div>
    """, unsafe_allow_html=True)

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
        st.markdown("</div>", unsafe_allow_html=True) 
        return

    # TAHAP 1: 3-TF ANALYSIS
    if decision and technical_ctx:
        st.markdown('<div class="sub-section"><div class="sub-title">TAHAP 1 — SIMPLIFIED WATERFALL (3-TF)</div>', unsafe_allow_html=True)
        
        fund = decision.get("fundamental", {})
        fund_flag = fund.get("flag", "GREEN")
        f_color = "check-fail" if fund_flag == "RED" else ("check-pass" if fund_flag == "GREEN" else "check-wait")
        st.markdown(f"**Fundamental Guard:** <span class='{f_color}'>{fund_flag}</span> <span style='font-size:0.8em'>({fund.get('reason', ['-'])[0]})</span>", unsafe_allow_html=True)
        
        col_h4, col_h1, col_m15 = st.columns(3)
        
        # --- LOGIC TEXT BUILDER ---
        
        # 1. H4 BOX
        h4 = technical_ctx.get("trend_h4", {})
        h4_valid = h4.get('valid')
        h4_color = "#10b981" if h4_valid else "#ef4444"
        
        if h4_valid:
            h4_title = f"💪 STRONG {h4.get('direction')}"
            h4_desc = f"ADX {h4.get('adx',0):.1f} > 20<br>Trend sangat jelas & kuat."
        else:
            h4_title = "😴 WEAK / SIDEWAYS"
            h4_desc = f"ADX {h4.get('adx',0):.1f} < 20<br>Tidak ada momentum tren."

        col_h4.markdown(f"""
        <div class="logic-box" style="border-left: 4px solid {h4_color};">
            <span class="logic-title">TF H4 (Arah Utama)</span>
            <span style="color: {h4_color}; font-weight:bold;">{h4_title}</span>
            <span class="logic-desc">{h4_desc}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # 2. H1 BOX
        h1 = technical_ctx.get("bias_h1", {})
        h1_aligned = h1.get('aligned')
        h1_color = "#10b981" if h1_aligned else "#ef4444"
        
        if h1_aligned:
            h1_title = "✅ MOMENTUM SELARAS"
            h1_desc = "Harga H1 bergerak searah<br>dengan Trend H4."
        else:
            h1_title = "⚠️ DIVERGENCE"
            h1_desc = "Harga H1 melawan arus H4.<br>Potensi koreksi/reversal."

        col_h1.markdown(f"""
        <div class="logic-box" style="border-left: 4px solid {h1_color};">
            <span class="logic-title">TF H1 (Validasi)</span>
            <span style="color: {h1_color}; font-weight:bold;">{h1_title}</span>
            <span class="logic-desc">{h1_desc}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # 3. M15 BOX (DETAIL TRIGGER)
        notes = decision.get("notes", [])
        m15_note = next((n for n in notes if "M15" in n), None)
        direction = h4.get("direction")
        
        m15_color = "#64748b" # Default Grey
        m15_title = "🔒 LOCKED"
        m15_desc = "Menunggu H4 & H1 Valid..."

        if not h4_valid:
            m15_desc = "Trend H4 tidak valid.<br>Sistem standby."
        elif not h1_aligned:
            m15_desc = "Bias H1 tidak selaras.<br>Menunggu harga sinkron."
        elif fund_flag == "RED":
            m15_color = "#ef4444"
            m15_title = "⛔ NEWS BLOCK"
            m15_desc = "Trading dihentikan karena<br>risiko fundamental tinggi."
        elif decision['status'] == "EXECUTE":
            m15_color = "#10b981"
            m15_title = "🚀 TRIGGER FIRED"
            clean_note = m15_note.replace("M15: ", "") if m15_note else "Impulse Confirmed"
            m15_desc = f"Setup Valid!<br>{clean_note}"
        else:
            # WAITING STATE DETAILED
            m15_color = "#f59e0b" # Orange
            m15_title = "👀 HUNTING SETUP"
            
            if direction == "LONG":
                m15_desc = "<b>Pantau Long:</b><br>1. Breakout Resistance<br>2. Rejection/Pinbar di Support"
            elif direction == "SHORT":
                m15_desc = "<b>Pantau Short:</b><br>1. Breakdown Support<br>2. Rejection/Pinbar di Resistance"
            else:
                m15_desc = "Menunggu pola candle..."

        col_m15.markdown(f"""
        <div class="logic-box" style="border-left: 4px solid {m15_color};">
            <span class="logic-title">TF M15 (Eksekusi)</span>
            <span style="color: {m15_color}; font-weight:bold;">{m15_title}</span>
            <span class="logic-desc">{m15_desc}</span>
        </div>
        """, unsafe_allow_html=True)

        # AI Verdict
        verdict_text = generate_human_verdict(symbol, decision, technical_ctx)

        st.markdown(f"""
        <div class="summary-box">
            <strong style="color: #6366f1;">📝 AI VERDICT (Analisa Akhir)</strong><br>
            {verdict_text.replace('\n', '<br>')}
        </div>
        """, unsafe_allow_html=True)

        # Execution Plan
        if decision["status"] == "EXECUTE":
            st.markdown('<div class="sub-section"><div class="sub-title">🎯 EXECUTION PLAN</div>', unsafe_allow_html=True)
            risk = decision.get("risk", {})
            r1, r2, r3 = st.columns(3)
            r1.metric("Direction", decision.get("direction"))
            r2.metric("Stop Loss", f"${risk.get('stop_loss'):,.4f}")
            r3.metric("Take Profit", f"${risk.get('take_profit'):,.4f}")
            st.success(f"Position Size: {risk.get('position_size')} Units (Confidence: {decision.get('confidence')*100:.0f}%)")

    st.markdown("</div>", unsafe_allow_html=True)

# =============================
# MAIN APP LOGIC
# =============================
st.title("AltaQuant • Institutional Grade DSS")
st.markdown("Automated Screening & Waterfall Analysis System")

screener = CryptoScreener()

with st.sidebar:
    st.title("🛡️ AltaQuant Control")
    mode = st.radio("Mode Operasi", ["Market Scanner (Auto)", "Single Analyzer"])
    
    if mode == "Single Analyzer":
        symbol = st.text_input("Symbol", "BTC/USDT").upper()
        equity = st.number_input("Equity ($)", 1000.0)
        run_btn = st.button("🚀 START ANALYSIS", type="primary")
    else:
        st.info("Scanner akan memindai Top 50 Volume Koin. Scanner otomatis BERHENTI setelah menemukan 3 Setup Valid.")
        run_scan = st.button("🔍 SCAN MARKET HUNTER", type="primary")

# ----------------------------------------
# MODE 1: MARKET SCANNER
# ----------------------------------------
if mode == "Market Scanner":
    if run_scan:
        st.header("🔍 Market Hunter Results")
        
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
                symbols = get_top_symbols(limit=50)
            except Exception as e:
                add_log(f"Connection Fatal Error: {e}")

        if not symbols:
            st.error("❌ **KONEKSI GAGAL!**")
            st.markdown("""
            **Diagnosa:**
            1. ISP memblokir akses ke Binance API.
            2. VPN belum aktif atau tidak meng-cover terminal Python.
            3. Timeout koneksi.
            
            **Solusi:** Aktifkan VPN, restart aplikasi Streamlit, dan coba lagi.
            """)
            st.stop()

        with st.status("🚀 Scanning Market...", expanded=True) as status:
            add_log(f"Connection Success. Found {len(symbols)} active markets.")
            st.write(f"Menganalisa {len(symbols)} koin dengan volume tertinggi...")
            
            found_candidates = []
            progress_bar = st.progress(0)
            
            for i, sym in enumerate(symbols):
                if len(found_candidates) >= 3:
                    add_log("[STOP] Target 3 Candidates Found.")
                    break
                
                progress_bar.progress((i + 1) / len(symbols))
                status.update(label=f"Scanning {sym} ({i+1}/{len(symbols)})...")
                
                dummy_fund = [{"keyword": "neutral", "impact": "medium"}]
                
                try:
                    screen_res = screener.run_screen(sym, dummy_fund)
                except Exception as e:
                    add_log(f"Error screening {sym}: {e}")
                    continue

                if screen_res.get("status") == "FAIL":
                    reasons = screen_res.get('reasons', [])
                    reason = reasons[0] if reasons else "Unknown"
                    add_log(f"   [X] {sym}: REJECTED ({reason})")
                    continue 
                
                add_log(f"   [!] {sym}: PASSED SCREEN. Deep Analyzing...")
                ctx = build_ai_context(sym)
                
                if not ctx: 
                    add_log(f"   [!] {sym}: Error Context Build (Data Fetch Failed)")
                    continue
                
                decision = final_decision(
                    technical_data=ctx,
                    fundamental_signals=dummy_fund,
                    equity=1000,
                    atr=ctx.get("atr", 0),
                    entry_price=ctx.get("price", 0)
                )
                
                if decision["status"] == "EXECUTE":
                    add_log(f"   💎 {sym}: DIAMOND FOUND! {decision['direction']}")
                    found_candidates.append({
                        "symbol": sym,
                        "screen": screen_res,
                        "decision": decision,
                        "ctx": ctx
                    })
                else:
                    status_reason = decision.get("status", "NO_TRADE")
                    if decision.get("notes"):
                        status_reason += f" ({decision['notes'][-1]})"
                    add_log(f"   [O] {sym}: NO TRADE ({status_reason})")
                    
            progress_bar.empty()
            status.update(label="✅ Hunting Complete", state="complete")
            
        st.divider()
        if not found_candidates:
            st.warning("⚠️ Market Hunter selesai. Tidak ada koin yang memenuhi kriteria 'Super Analyst'.")
            st.info("Tips: Market mungkin sedang 'Choppy' atau Sideways parah. Coba lagi nanti.")
        else:
            st.success(f"💎 Ditemukan {len(found_candidates)} Setup Valid!")
            for cand in found_candidates:
                render_analysis_card(
                    cand['symbol'], 
                    cand['screen'], 
                    cand['decision'], 
                    cand['ctx']
                )

# ----------------------------------------
# MODE 2: SINGLE ANALYZER
# ----------------------------------------
elif mode == "Single Analyzer":
    if run_btn:
        st.header(f"Deep Analysis: {symbol}")
        
        with st.spinner("🔍 Sedang menganalisa Market & Berita..."):
            
            news = get_cached_news(symbol)
            fund_signals = [{"keyword": news, "impact": "medium"}]
            
            screen_res = screener.run_screen(symbol, fund_signals)
            
            decision = None
            ctx = None
            
            if screen_res["status"] == "PASS":
                ctx = build_ai_context(symbol)
                if ctx:
                    decision = final_decision(
                        technical_data=ctx,
                        fundamental_signals=fund_signals,
                        equity=equity,
                        atr=ctx.get("atr", 0),
                        entry_price=ctx.get("price", 0)
                    )
            
            render_analysis_card(symbol, screen_res, decision, ctx)
            
            with st.expander("📄 Read News Context (Cached 5 Min)", expanded=False):
                st.info(f"Berita diambil dari cache (Update tiap 5 menit agar hemat API).\n\n{news}")