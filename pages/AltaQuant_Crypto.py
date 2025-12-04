import streamlit as st
import plotly.graph_objects as go
import json
import re

# =============================
# BACKEND IMPORT
# =============================
from backend.crypto_data import build_ai_context
from backend.ai_engine import final_decision

# ❌ DEPRECATED / NOT USED (kept as comment)
# from backend.fundamental import analyze_fundamental
# from backend.ai_engine import run_ai_pipeline

from backend.news import get_crypto_news

# =============================
# PAGE CONFIG
# =============================
st.set_page_config(
    page_title="AltaQuant Pro",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================
# GLOBAL STYLE
# =============================
st.markdown("""
<style>
:root {
    --bull: #10b981;
    --bear: #ef4444;
    --wait: #64748b;
}
.block {
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 20px;
}
.label {
    font-size: 0.8rem;
    color: #94a3b8;
    text-transform: uppercase;
}
.value {
    font-size: 1.1rem;
    font-weight: bold;
}
.verdict {
    padding: 16px;
    border-left: 4px solid;
    background: rgba(255,255,255,0.03);
    font-style: italic;
}
</style>
""", unsafe_allow_html=True)

# =============================
# SIDEBAR
# =============================
with st.sidebar:
    st.title("AltaQuant Control Panel")

    symbol = st.text_input("Trading Pair", "BTCUSDT")
    mode = st.selectbox("Mode", ["Crypto Futures", "Spot"])

    st.divider()

    user_chart_context = st.text_area(
        "Chart / Pattern Context (Optional)",
        placeholder=(
            "Example:\n"
            "- H4 bullish structure (HH HL)\n"
            "- Ascending triangle\n"
            "- Context only, not a trigger"
        )
    )

    st.caption("ℹ️ Chart pattern is CONTEXT ONLY. No auto detection.")

    equity = st.number_input("Account Equity ($)", value=1000.0)
    entry_price = st.number_input("Assumed Entry Price", value=0.0)
    atr = st.number_input("ATR (M15)", value=0.0)

    run = st.button("RUN ANALYSIS", type="primary")

# =============================
# MAIN
# =============================
st.title("AltaQuant Hybrid Analytics")
st.caption("Multi-Timeframe • Liquidity • Fundamental-Gated")

if run:
    with st.status("Running institutional audit pipeline...", expanded=True):

        # =============================
        # FUNDAMENTAL INPUT
        # =============================
        st.write("📰 Fetching crypto news & macro events...")
        news_text = get_crypto_news(symbol)

        st.write("✅ Fundamental signals collected")

        # =============================
        # TECHNICAL CONTEXT
        # =============================
        st.write("📊 Building multi-timeframe technical context...")
        technical_context = build_ai_context(
        symbol.replace("/", ""),  # 🔥 FIX SYMBOL FORMAT
        user_chart_context
        )

        if technical_context is None:
            st.error("Market data unavailable or insufficient candles.")
            st.stop()

        # =============================
        # FINAL DECISION ENGINE
        # =============================
        st.write("🧠 Executing AltaQuant Core Engine...")
        result = final_decision(
            technical_data=technical_context,
            fundamental_signals=news_text,
            equity=equity,
            atr=atr,
            entry_price=entry_price
        )

        # =============================
        # OUTPUT
        # =============================
        status = result.get("status", "WAIT")
        direction = result.get("direction", "WAIT")

        color = (
            "var(--bull)" if direction == "LONG" else
            "var(--bear)" if direction == "SHORT" else
            "var(--wait)"
        )

        st.markdown(f"""
        <div class="block">
            <div class="label">Final Status</div>
            <div class="value" style="color:{color};">{status}</div>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3)

        col1.markdown(f"""
        <div class="block">
            <div class="label">Direction</div>
            <div class="value">{direction}</div>
        </div>
        """, unsafe_allow_html=True)

        col2.markdown(f"""
        <div class="block">
            <div class="label">Confidence</div>
            <div class="value">{result.get("confidence", "-")}</div>
        </div>
        """, unsafe_allow_html=True)

        col3.markdown(f"""
        <div class="block">
            <div class="label">Risk</div>
            <div class="value">{result.get("risk", {})}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="verdict" style="border-color:{color}">
            <strong>Fundamental Assessment:</strong><br>
            {json.dumps(result.get("fundamental", {}), indent=2)}
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        st.subheader("Engine Output (Debug)")
        st.json(result)

# =============================
# LEGACY BLOCK (DISABLED)
# =============================

# ❌ OLD PIPELINE — NO LONGER USED
# user_pattern_context = st.text_input("Chart Pattern Context (optional)")
# if st.button("Run Legacy Pipeline"):
#     decision = run_ai_pipeline(
#         technical_data=st.session_state["technical"],
#         fundamental_signals=st.session_state["fundamental"],
#         equity=equity,
#         atr=atr,
#         entry_price=entry_price
#     )
#     st.json(decision)
