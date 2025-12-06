import streamlit as st
import pandas as pd
import json
import time

# =============================
# BACKEND IMPORT
# =============================
from backend.crypto.data import build_ai_context
from backend.crypto.engine import final_decision
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
# GLOBAL STYLE
# =============================
st.markdown("""
<style>
/* Card Styling */
.metric-card {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 15px;
    margin-bottom: 10px;
}
.metric-title {
    font-size: 0.85rem;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 5px;
}
.metric-value {
    font-size: 1.2rem;
    font-weight: 700;
    color: #f8fafc;
}
.metric-sub {
    font-size: 0.8rem;
    margin-top: 5px;
}

/* Status Colors */
.status-green { color: #10b981 !important; }
.status-red { color: #ef4444 !important; }
.status-yellow { color: #f59e0b !important; }

/* Audit Steps */
.step-container {
    display: flex;
    margin-bottom: 12px;
    background: #0f172a;
    padding: 12px;
    border-radius: 8px;
    border-left: 4px solid #334155;
}
.step-icon { font-size: 1.5rem; margin-right: 15px; }
.step-content { flex-grow: 1; }
.step-header { font-weight: bold; color: #e2e8f0; }
.step-desc { font-size: 0.9rem; color: #cbd5e1; }

</style>
""", unsafe_allow_html=True)

# =============================
# SIDEBAR
# =============================
with st.sidebar:
    st.header("🎛️ Control Panel")
    symbol = st.text_input("Symbol", "BTC/USDT").upper()
    
    with st.expander("⚙️ Parameter Simulasi"):
        equity = st.number_input("Equity ($)", value=1000.0)
        entry_price = st.number_input("Entry Price (Optional)", value=0.0)
    
    st.info("💡 **Mode Super Analyst:** Sistem akan menampilkan detail setiap timeframe meskipun keputusan akhirnya No Trade.")
    
    run_btn = st.button("🚀 RUN ANALYST", type="primary")

# =============================
# HELPER FUNCTIONS
# =============================
def render_step(title, status, detail, sub_detail=None):
    """Visualisasi Step Waterfall"""
    if status == "PASS":
        border_color = "#10b981" # Green
        icon = "✅"
    elif status == "FAIL":
        border_color = "#ef4444" # Red
        icon = "⛔"
    else:
        border_color = "#64748b" # Grey/Skip
        icon = "⏭️"
        
    st.markdown(f"""
    <div class="step-container" style="border-left-color: {border_color};">
        <div class="step-icon">{icon}</div>
        <div class="step-content">
            <div class="step-header">{title}</div>
            <div class="step-desc">{detail}</div>
            {f'<div class="metric-sub" style="color:#94a3b8">{sub_detail}</div>' if sub_detail else ''}
        </div>
    </div>
    """, unsafe_allow_html=True)

# =============================
# MAIN APP
# =============================
st.title("AltaQuant • Super Analyst Dashboard")
st.caption("Institutional Waterfall Analysis: H4 ➡️ H1 ➡️ M30 ➡️ M15")

if run_btn:
    # --- PHASE 1: GATHERING DATA ---
    with st.status("🔍 Scanning Market Structure...", expanded=True) as status:
        st.write("1️⃣ Fetching Fundamental & Sentiment...")
        news_text = get_crypto_news(symbol)
        fund_signals = [{"keyword": news_text, "impact": "medium"}]
        
        st.write("2️⃣ Downloading Multi-Timeframe Data (H4, H1, M30, M15)...")
        ctx = build_ai_context(symbol)
        
        if ctx is None:
            status.update(label="❌ Data Fetch Failed! Check Symbol or Connection.", state="error")
            st.stop()
            
        st.write("3️⃣ Running AI Decision Engine...")
        
        # Prepare params
        atr_val = ctx.get("atr", 0.0)
        current_price = ctx.get("price", 0.0)
        use_entry = entry_price if entry_price > 0 else current_price
        
        decision = final_decision(
            technical_data=ctx,
            fundamental_signals=fund_signals,
            equity=equity,
            atr=atr_val,
            entry_price=use_entry
        )
        
        status.update(label="✅ Analysis Complete", state="complete")

    # --- PHASE 2: DASHBOARD DISPLAY ---
    
    # 1. TOP LEVEL DECISION
    final_status = decision.get("status")
    direction = decision.get("direction")
    confidence = decision.get("confidence", 0) * 100
    
    # Determine Color
    if final_status == "EXECUTE":
        main_color = "status-green"
        bg_callout = "rgba(16, 185, 129, 0.1)"
    elif final_status in ["NO_TRADE", "BLOCKED_BY_FUNDAMENTAL"]:
        main_color = "status-red"
        bg_callout = "rgba(239, 68, 68, 0.1)"
    else:
        main_color = "status-yellow"
        bg_callout = "rgba(245, 158, 11, 0.1)"

    st.markdown(f"""
    <div style="background: {bg_callout}; padding: 20px; border-radius: 12px; border: 1px solid currentColor; margin-bottom: 25px; text-align: center;">
        <h2 style="margin:0; font-size: 2.5rem;" class="{main_color}">{final_status}</h2>
        <p style="margin:5px 0 0 0; font-size: 1.1rem; opacity: 0.8;">
            Direction: <strong>{direction}</strong> • Confidence: <strong>{confidence:.1f}%</strong>
        </p>
    </div>
    """, unsafe_allow_html=True)

    # 2. SPLIT VIEW: RAW DATA vs LOGIC FLOW
    tab1, tab2, tab3 = st.tabs(["🌊 Waterfall Analysis (Logic)", "📊 Market Context (Raw Data)", "🛡️ Fundamental & News"])
    
    with tab1:
        st.subheader("Kenapa Hasilnya Demikian?")
        st.caption("Sistem mengecek aturan secara berurutan. Jika satu langkah gagal (⛔), langkah berikutnya di-skip.")
        
        # --- EXTRACT LOGIC STATUS ---
        # Note: Kita ambil data raw dari ctx untuk menampilkan "Alasan" meskipun engine sudah stop
        
        # STEP 1: H4
        h4 = ctx.get("trend_h4", {})
        h4_pass = h4.get("valid", False)
        h4_detail = f"Trend: {h4.get('direction')} | ADX: {h4.get('adx', 0):.2f}"
        render_step(
            "STEP 1: H4 Major Trend (Anchor)",
            "PASS" if h4_pass else "FAIL",
            f"Status: {'VALID' if h4_pass else 'INVALID'}",
            h4_detail
        )
        
        # STEP 2: H1
        h1 = ctx.get("bias_h1", {})
        h1_aligned = h1.get("aligned", False)
        h1_detail = h1.get("reason", "N/A")
        
        # H1 Logic: Hanya relevan jika H4 Pass
        if h4_pass:
            render_step(
                "STEP 2: H1 Bias Confirmation",
                "PASS" if h1_aligned else "FAIL",
                f"Status: {'ALIGNED' if h1_aligned else 'DIVERGENCE'}",
                h1_detail
            )
        else:
            render_step("STEP 2: H1 Bias Confirmation", "SKIP", "Skipped karena H4 Invalid")

        # STEP 3: M30
        # Cek notes dari decision untuk melihat apakah M30 dicek
        notes = decision.get("notes", [])
        m30_note = next((n for n in notes if "M30" in n), None)
        
        if h4_pass and h1_aligned:
            # Jika M30 note ada dan positif (tidak ada kata Failed)
            m30_pass = m30_note and "Failed" not in m30_note
            render_step(
                "STEP 3: M30 Liquidity Setup",
                "PASS" if m30_pass else "FAIL",
                m30_note if m30_note else "No Liquidity Sweep Detected",
                "Mencari: Liquidity Sweep (Wick) + Reclaim Area"
            )
        else:
             render_step("STEP 3: M30 Liquidity Setup", "SKIP", "Skipped karena struktur makro (H4/H1) belum valid")

        # STEP 4: M15
        m15_note = next((n for n in notes if "M15" in n), None)
        if h4_pass and h1_aligned and m30_note and "Failed" not in m30_note:
            m15_pass = m15_note and "Failed" not in m15_note
            render_step(
                "STEP 4: M15 Execution Trigger",
                "PASS" if m15_pass else "FAIL",
                m15_note if m15_note else "Momentum/Volume belum valid",
                "Syarat: Candle Impulsif + Volume > MA20"
            )
        else:
             render_step("STEP 4: M15 Execution Trigger", "SKIP", "Menunggu Setup M30 Valid")

    with tab2:
        st.subheader("Indikator & Angka Mentah")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.markdown('<div class="metric-title">Price & ATR</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-value">${current_price:,.2f}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-sub">ATR (15m): {atr_val:.2f}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
        with c2:
            h4_dir = ctx.get("trend_h4", {}).get("direction", "-")
            h4_adx = ctx.get("trend_h4", {}).get("adx", 0)
            adx_color = "status-green" if h4_adx >= 20 else "status-red"
            
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.markdown('<div class="metric-title">H4 Strength</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-value">{h4_dir}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-sub {adx_color}">ADX: {h4_adx:.2f} (Threshold: 20)</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
        with c3:
            h1_status = "✅ Aligned" if ctx.get("bias_h1", {}).get("aligned") else "⚠️ Divergence"
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.markdown('<div class="metric-title">H1 Bias</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-value">{h1_status}</div>', unsafe_allow_html=True)
            st.markdown('<div class="metric-sub">Price vs EMA50 Relation</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        st.info("ℹ️ **Cara Baca:** Jika ADX < 20, Market sedang *Choppy*/Sideways. Trend Following akan sering gagal. Sistem otomatis skip.")

    with tab3:
        st.subheader("Fundamental Intelligence")
        
        fund = decision.get("fundamental", {})
        flag = fund.get("flag", "GREY")
        
        if flag == "RED":
            st.error(f"🛑 CRITICAL BLOCK: {fund.get('reason')}")
        elif flag == "YELLOW":
            st.warning(f"⚠️ WARNING (Reduce Size): {fund.get('reason')}")
        else:
            st.success("✅ Fundamental Clean / Neutral")
            
        with st.expander("📄 Baca Berita Raw (Sumber Analisa)", expanded=True):
            st.write(news_text)

    # 3. RISK CALCULATION (If Executable)
    if final_status == "EXECUTE":
        st.divider()
        st.subheader("🎯 Trade Plan (Execution)")
        risk = decision.get("risk", {})
        
        rc1, rc2, rc3 = st.columns(3)
        rc1.success(f"**STOP LOSS:** {risk.get('stop_loss')}")
        rc2.info(f"**TAKE PROFIT:** {risk.get('take_profit')}")
        rc3.warning(f"**SIZE:** {risk.get('position_size')} Units")