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
    
    .logic-box { background: #0f172a; padding: 10px; border-radius: 6px; font-size: 0.85rem; margin-bottom: 5px; height: 100%; }
    
    /* Terminal Log Style */
    .terminal-log {
        background-color: #0f172a;
        color: #10b981;
        font-family: 'Courier New', monospace;
        padding: 10px;
        border-radius: 5px;
        border: 1px solid #334155;
        height: 150px;
        overflow-y: auto;
        font-size: 0.8rem;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# =============================
# HELPER: RENDER CARD
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
        main_status = "NO TRADE (WAIT)"
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

    if decision and technical_ctx:
        st.markdown('<div class="sub-section"><div class="sub-title">TAHAP 1 — WATERFALL ANALYSIS</div>', unsafe_allow_html=True)
        fund = decision.get("fundamental", {})
        fund_flag = fund.get("flag", "GREEN")
        f_color = "check-fail" if fund_flag == "RED" else ("check-pass" if fund_flag == "GREEN" else "check-wait")
        st.markdown(f"**Fundamental Guard:** <span class='{f_color}'>{fund_flag}</span> <span style='font-size:0.8em'>({fund.get('reason', ['-'])[0]})</span>", unsafe_allow_html=True)
        
        col_h4, col_h1, col_m30, col_m15 = st.columns(4)
        h4 = technical_ctx.get("trend_h4", {})
        col_h4.markdown(f"""<div class="logic-box" style="border-left:3px solid {'#10b981' if h4.get('valid') else '#ef4444'}"><strong>TF H4 (Anchor)</strong><br>Dir: {h4.get('direction')}<br>ADX: {h4.get('adx',0):.1f}</div>""", unsafe_allow_html=True)
        
        h1 = technical_ctx.get("bias_h1", {})
        col_h1.markdown(f"""<div class="logic-box" style="border-left:3px solid {'#10b981' if h1.get('aligned') else '#ef4444'}"><strong>TF H1 (Bias)</strong><br>{'Aligned' if h1.get('aligned') else 'Divergence'}</div>""", unsafe_allow_html=True)
        
        notes = decision.get("notes", [])
        m30_note = next((n for n in notes if "M30" in n), "Skipped")
        m30_ok = "Failed" not in m30_note and "Skipped" not in m30_note
        col_m30.markdown(f"""<div class="logic-box" style="border-left:3px solid {'#10b981' if m30_ok else '#64748b'}"><strong>TF M30 (Setup)</strong><br>{m30_note}</div>""", unsafe_allow_html=True)
        
        m15_note = next((n for n in notes if "M15" in n), "Skipped")
        m15_ok = "Confirmed" in m15_note
        col_m15.markdown(f"""<div class="logic-box" style="border-left:3px solid {'#10b981' if m15_ok else '#64748b'}"><strong>TF M15 (Exec)</strong><br>{m15_note}</div>""", unsafe_allow_html=True)

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
# MODE 1: MARKET SCANNER (AUTO HUNTER)
# ----------------------------------------
if mode == "Market Scanner":
    if run_scan:
        st.header("🔍 Market Hunter Results")
        
        # Area Log
        log_placeholder = st.empty()
        logs = []

        def add_log(msg):
            logs.insert(0, f"> {msg}")
            # Tampilkan 8 baris terakhir
            log_text = "\n".join(logs[:8])
            log_placeholder.markdown(f"```bash\n{log_text}\n```")

        # 1. Fetch Top Symbols
        with st.status("📡 Initializing Scanner...", expanded=True) as status:
            add_log("Connecting to Binance Futures API...")
            try:
                # Mengambil data dengan batasan limit 50
                symbols = get_top_symbols(limit=50)
            except Exception as e:
                symbols = []
            
            # --- PENGECEKAN KONEKSI ---
            if not symbols:
                status.update(label="❌ CONNECTION FAILED!", state="error")
                st.error("Gagal terhubung ke Exchange! Tidak ada data simbol yang diterima.")
                st.warning("⚠️ **Solusi:** Aktifkan VPN Anda sekarang (Binance diblokir di Indonesia) dan coba lagi.")
                st.stop() # Berhenti di sini
            # ---------------------------

            add_log(f"Connection Success. Found {len(symbols)} active markets.")
            st.write(f"Didapat {len(symbols)} koin aktif. Memulai Hunting...")
            
            found_candidates = []
            progress_bar = st.progress(0)
            
            # 2. Scanning Loop
            for i, sym in enumerate(symbols):
                # STOP CONDITION
                if len(found_candidates) >= 3:
                    add_log("[STOP] Target 3 Candidates Found.")
                    break
                
                # Update Progress
                progress_bar.progress((i + 1) / len(symbols))
                
                # A. Screening Tahap 0
                add_log(f"Scanning {sym} ({i+1}/{len(symbols)})...")
                dummy_fund = [{"keyword": "neutral", "impact": "medium"}]
                
                # Jalankan Screener
                try:
                    screen_res = screener.run_screen(sym, dummy_fund)
                except Exception as e:
                    add_log(f"Error screening {sym}: {e}")
                    continue

                if screen_res["status"] == "FAIL":
                    reason = screen_res['reasons'][0] if screen_res['reasons'] else "Unknown"
                    add_log(f"   [X] REJECTED: {reason}")
                    continue 
                
                # B. Deep Analysis
                add_log(f"   [!] PASSED SCREEN. Deep Analyzing...")
                ctx = build_ai_context(sym)
                if not ctx: 
                    add_log("   [!] Error: Context Build Failed")
                    continue
                
                decision = final_decision(
                    technical_data=ctx,
                    fundamental_signals=dummy_fund,
                    equity=1000,
                    atr=ctx.get("atr", 0),
                    entry_price=ctx.get("price", 0)
                )
                
                # C. Check Result
                if decision["status"] == "EXECUTE":
                    add_log(f"   💎 DIAMOND FOUND! {decision['direction']}")
                    found_candidates.append({
                        "symbol": sym,
                        "screen": screen_res,
                        "decision": decision,
                        "ctx": ctx
                    })
                else:
                    status_reason = decision.get("status", "NO_TRADE")
                    if decision.get("notes"):
                        # Ambil note terakhir sebagai alasan singkat
                        status_reason += f" ({decision['notes'][-1]})"
                    add_log(f"   [O] NO TRADE: {status_reason}")
                    
            progress_bar.empty()
            status.update(label="✅ Hunting Complete", state="complete")
            
        # 3. Display Results
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
        
        with st.spinner("Analysing..."):
            news = get_crypto_news(symbol)
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
            
            with st.expander("📄 Read News Context"):
                st.write(news)