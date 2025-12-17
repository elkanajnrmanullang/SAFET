import streamlit as st
import pandas as pd
import time
from datetime import datetime

try:
    from backend.crypto.pipeline import pipeline
    from backend.crypto.screener import CryptoScreener
    from backend.crypto.data import get_top_symbols, fetch_market_data
    from backend.core.news import get_crypto_news
    
    screener = CryptoScreener()
    BACKEND_READY = True
except ImportError as e:
    st.error(f"Backend Error: {e}")
    BACKEND_READY = False

st.set_page_config(
    page_title="AltaQuant System",
    page_icon="https://img.icons8.com/fluency/48/artificial-intelligence.png",
    layout="wide",
    initial_sidebar_state="collapsed"
)

ASSETS = {
    "logo": "https://img.icons8.com/fluency/96/artificial-intelligence.png",
    "dashboard": "https://img.icons8.com/fluency/48/dashboard-layout.png",
    "workspace": "https://img.icons8.com/fluency/48/work-station.png",
    "history": "https://img.icons8.com/fluency/48/order-history.png",
    "diamond": "https://img.icons8.com/fluency/48/diamond.png",
    "shield": "https://img.icons8.com/fluency/48/shield.png",
    "eye": "https://img.icons8.com/fluency/48/visible.png",
    "news": "https://img.icons8.com/fluency/48/news.png",
    "up": "https://img.icons8.com/fluency/48/bullish.png",
    "down": "https://img.icons8.com/fluency/48/bearish.png",
    "banner": "https://images.unsplash.com/photo-1639322537228-f710d846310a?q=80&w=2832&auto=format&fit=crop"
}

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;500;700&family=Inter:wght@300;400;600&display=swap');
    
    :root {{
        --bg-deep: #020617;
        --glass-bg: rgba(15, 23, 42, 0.6);
        --glass-border: rgba(255, 255, 255, 0.08);
        --primary: #6366f1;
        --success: #10b981;
        --danger: #ef4444;
        --warning: #f59e0b;
        --text-main: #f8fafc;
        --text-sub: #94a3b8;
    }}

    .stApp {{
        background-color: var(--bg-deep);
        background-image: radial-gradient(circle at 50% 0%, #1e1b4b 0%, var(--bg-deep) 60%);
        font-family: 'Inter', sans-serif;
        color: var(--text-main);
    }}
    
    #MainMenu, footer, header {{visibility: hidden;}}
    [data-testid="stSidebar"] {{display: none;}}
    
    .nav-container {{
        display: flex;
        justify-content: center;
        align-items: center;
        background: rgba(15, 23, 42, 0.8);
        backdrop-filter: blur(16px);
        border: 1px solid var(--glass-border);
        border-radius: 100px;
        padding: 10px 40px;
        margin: 20px auto 40px auto;
        width: fit-content;
        gap: 20px;
        box-shadow: 0 10px 40px rgba(0,0,0,0.5);
    }}
    
    .nav-brand {{
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 700;
        background: linear-gradient(90deg, #fff, var(--primary));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-right: 20px;
    }}

    .aq-card {{
        background: var(--glass-bg);
        border: 1px solid var(--glass-border);
        border-radius: 16px;
        padding: 24px;
        backdrop-filter: blur(12px);
        box-shadow: 0 4px 20px rgba(0,0,0,0.2);
        margin-bottom: 20px;
    }}

    h1, h2, h3 {{ font-family: 'Space Grotesk', sans-serif; color: var(--text-main); }}
    .sub-text {{ color: var(--text-sub); font-size: 0.9rem; }}
    
    .status-badge {{
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }}
    .status-exec {{ background: rgba(16, 185, 129, 0.2); color: var(--success); border: 1px solid var(--success); }}
    .status-wait {{ background: rgba(245, 158, 11, 0.2); color: var(--warning); border: 1px solid var(--warning); }}
    .status-block {{ background: rgba(239, 68, 68, 0.2); color: var(--danger); border: 1px solid var(--danger); }}

    div.stButton > button {{
        background: rgba(255,255,255,0.05);
        border: 1px solid var(--glass-border);
        color: white;
        border-radius: 8px;
        transition: all 0.3s;
        width: 100%;
    }}
    div.stButton > button:hover {{
        background: var(--primary);
        border-color: var(--primary);
    }}
    
    .icon-sm {{ width: 20px; vertical-align: middle; margin-right: 8px; }}
    .ticker-val {{ font-family: 'Space Grotesk'; font-size: 1.1rem; }}
</style>
""", unsafe_allow_html=True)

if 'page' not in st.session_state:
    st.session_state.page = 'home'

def nav_to(page):
    st.session_state.page = page

@st.cache_data(ttl=60)
def get_market_data():
    try:
        coins = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "ADA/USDT"]
        data = []
        for sym in coins:
            df = fetch_market_data(sym, "1h", limit=2)
            if df is not None and not df.empty:
                curr = df['close'].iloc[-1]
                prev = df['open'].iloc[-1]
                chg = ((curr - prev) / prev) * 100
                data.append({"s": sym.split('/')[0], "p": curr, "c": chg})
        return data
    except:
        return []

def render_navbar():
    st.markdown("""
    <div class="nav-container">
        <div class="nav-brand">ALTAQUANT</div>
    </div>
    """, unsafe_allow_html=True)
    
    c1, c2, c3, c4, c5 = st.columns([3, 1, 1, 1, 3])
    with c2:
        if st.button("DASHBOARD", use_container_width=True): nav_to('home')
    with c3:
        if st.button("WORKSPACE", use_container_width=True): nav_to('workspace')
    with c4:
        if st.button("HISTORY", use_container_width=True): nav_to('history')
    
    st.markdown("<div style='margin-bottom: 20px'></div>", unsafe_allow_html=True)

def page_home():
    st.image(ASSETS['banner'], use_container_width=True)
    st.markdown("""
    <div style="margin-top: -80px; position: relative; padding: 20px; background: linear-gradient(to top, #020617, transparent);">
        <h1 style="font-size: 3rem; margin-bottom: 0;">MARKET OVERVIEW</h1>
        <p class="sub-text">Real-time Institutional Crypto Analytics</p>
    </div>
    """, unsafe_allow_html=True)

    data = get_market_data()
    if data:
        cols = st.columns(len(data))
        for i, d in enumerate(data):
            color = "#10b981" if d['c'] >= 0 else "#ef4444"
            with cols[i]:
                st.markdown(f"""
                <div class="aq-card" style="padding: 15px; text-align: center;">
                    <div style="font-weight:bold; color: #94a3b8;">{d['s']}</div>
                    <div class="ticker-val">${d['p']:,.2f}</div>
                    <div style="color: {color}; font-size: 0.9rem;">{d['c']:+.2f}%</div>
                </div>
                """, unsafe_allow_html=True)

    c_news, c_active = st.columns([1, 1])
    with c_news:
        st.markdown(f"### <img src='{ASSETS['news']}' class='icon-sm'> Global Intelligence", unsafe_allow_html=True)
        btc_news = get_crypto_news("BTC")
        st.markdown(f"""
        <div class="aq-card">
            <div style="line-height:1.6; color:#f8fafc;">{btc_news}</div>
        </div>
        """, unsafe_allow_html=True)

    with c_active:
        st.markdown(f"### <img src='{ASSETS['up']}' class='icon-sm'> Performance Preview", unsafe_allow_html=True)
        st.info("System Live. Connect to Workspace to start analysis.")

def render_result_card(symbol, res, scr):
    if res is None: res = {}
    if scr is None: scr = {}
    
    decision = res.get("final_decision") or {}
    risk = res.get("risk") or {}
    tech = res.get("technical_signal") or {}
    
    status = decision.get("status", "WAIT")
    
    if status == "EXECUTE":
        border_col = "#10b981"
        badge_cls = "status-exec"
        icon = ASSETS['diamond']
    elif status == "WAIT_FOR_TRIGGER":
        border_col = "#f59e0b"
        badge_cls = "status-wait"
        icon = ASSETS['eye']
    else:
        border_col = "#ef4444"
        badge_cls = "status-block"
        icon = ASSETS['shield']

    st.markdown(f"""
<div class="aq-card" style="border-left: 5px solid {border_col};">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 20px;">
        <div style="display:flex; align-items:center; gap:15px;">
            <img src="{icon}" width="40">
            <div>
                <h2 style="margin:0; font-size:1.5rem;">{symbol}</h2>
                <span style="color:#94a3b8; font-size:0.9rem;">{decision.get('strategy', 'Standard')}</span>
            </div>
        </div>
        <div class="status-badge {badge_cls}">{status}</div>
    </div> 
    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:20px; margin-bottom:20px;">
        <div style="background:rgba(255,255,255,0.03); padding:15px; border-radius:12px;">
            <h4 style="margin-top:0; color:#cbd5e1;">Technical Matrix</h4>
            <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                <span>Confidence</span>
                <strong>{decision.get('confidence', 0)}%</strong>
            </div>
            <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                <span>H4 Structure</span>
                <strong>{tech.get('direction', 'NEUTRAL')}</strong>
            </div>
            <div style="display:flex; justify-content:space-between;">
                <span>Vol. Gate</span>
                <strong>{tech.get('volatility', 'NORMAL')}</strong>
            </div>
        </div>       
        <div style="background:rgba(255,255,255,0.03); padding:15px; border-radius:12px;">
            <h4 style="margin-top:0; color:#cbd5e1;">Risk Parameters</h4>
            <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                <span>Entry</span>
                <strong style="color:#6366f1;">${risk.get('entry', 0):,.4f}</strong>
            </div>
            <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                <span>Stop Loss</span>
                <strong style="color:#ef4444;">${risk.get('stop_loss', 0):,.4f}</strong>
            </div>
            <div style="display:flex; justify-content:space-between;">
                <span>Take Profit</span>
                <strong style="color:#10b981;">${risk.get('take_profit', 0):,.4f}</strong>
            </div>
        </div>
    </div>  
    <div style="background:rgba(99, 102, 241, 0.1); padding:15px; border-radius:12px; border:1px solid rgba(99, 102, 241, 0.2);">
        <strong style="color:#818cf8;">AI EXECUTIVE SUMMARY</strong>
        <p style="margin-top:5px; margin-bottom:0; font-style:italic; color:#e2e8f0;">
            "{res.get('explainability', 'Analysis narrative unavailable.')}"
        </p>
    </div>
</div>
    """, unsafe_allow_html=True)

def page_workspace():
    st.markdown(f"""
    <div style="display:flex; align-items:center; gap:15px; margin-bottom:30px;">
        <img src="{ASSETS['workspace']}" width="50">
        <div>
            <h1 style="margin:0;">ANALYST WORKSPACE</h1>
            <p class="sub-text">AI-Powered Scanning & Technical Analysis Engine</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="aq-card">', unsafe_allow_html=True)
    mode = st.radio("OPERATION MODE", ["Auto-Scanner", "Single Analyzer"], horizontal=True)
    st.markdown("---")
    
    if mode == "Single Analyzer":
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1:
            symbol = st.text_input("TOKEN PAIR", "BTC/USDT").upper()
        with c2:
            uploaded = st.file_uploader("Chart Image (Vision AI)", type=['jpg', 'png'])
        with c3:
            st.write("")
            st.write("")
            run_btn = st.button("RUN ANALYSIS")
            
        if run_btn:
            with st.status("Processing Pipeline...", expanded=True) as status:
                try:
                    scr = screener.run_screen(symbol)
                    img_bytes = uploaded.getvalue() if uploaded else None
                    res = pipeline.run(symbol, user_image_bytes=img_bytes)
                    status.update(label="Complete", state="complete")
                    render_result_card(symbol, res, scr)
                except Exception as e:
                    st.error(f"Analysis Error: {str(e)}")
                    status.update(label="Error", state="error")
    
    else: 
        c1, c2 = st.columns([3, 1])
        with c1:
            limit = st.slider("Scan Limit (Top Volume)", 5, 50, 10)
        with c2:
            st.write("")
            scan_btn = st.button("START SCAN")
            
        if scan_btn:
            st.write("### Live Scanner Feed")
            log_col, res_col = st.columns([1, 2])
            
            with log_col:
                st.caption("SYSTEM LOGS")
                log_placeholder = st.empty()
                
            with res_col:
                premium_cont = st.container()
                watch_cont = st.container()
                with premium_cont: st.markdown("#### PREMIUM SIGNALS")
                with watch_cont: st.markdown("#### WATCHLIST")

            logs = []
            def add_log(msg):
                logs.insert(0, f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
                log_text = "\n".join(logs[:20])
                log_placeholder.code(log_text, language="bash")

            add_log("Connecting to Exchange Node...")
            try:
                symbols = get_top_symbols(limit)
                add_log(f"Fetched {len(symbols)} symbols.")
            except Exception as e:
                add_log(f"Connection Failed: {str(e)}")
                symbols = []
                st.error("Connection error detected.")

            if symbols:
                prog_bar = st.progress(0)
                for i, sym in enumerate(symbols):
                    prog_bar.progress((i+1)/len(symbols))
                    add_log(f"Scanning {sym}...")
                    try:
                        scr = screener.run_screen(sym)
                        if scr['status'] == 'FAIL':
                            fail_reason = scr.get('reasons', ['Unknown'])[0]
                            add_log(f"-> REJECTED: {fail_reason}")
                            continue 
                        
                        add_log(f"-> PASSED. Running AI...")
                        res = pipeline.run(sym)
                        decision = res.get('final_decision') or {}
                        status_code = decision.get('status', 'WAIT')
                        
                        if status_code == "EXECUTE":
                            add_log(f"SIGNAL FOUND: {sym}")
                            with premium_cont:
                                render_result_card(sym, res, scr)
                        elif status_code == "WAIT_FOR_TRIGGER":
                            add_log(f"-> Watchlist added: {sym}")
                            with watch_cont:
                                render_result_card(sym, res, scr)
                        else:
                            add_log(f"-> Result: {status_code}")
                            
                    except Exception as e:
                        add_log(f"-> ERROR: {str(e)}")
                        continue
                
                prog_bar.empty()
                add_log("SCAN COMPLETE.")
                st.success("Scan Finished.")
    
    st.markdown('</div>', unsafe_allow_html=True)

def page_history():
    st.markdown(f"""
    <div style="display:flex; align-items:center; gap:15px; margin-bottom:30px;">
        <img src="{ASSETS['history']}" width="50">
        <div>
            <h1 style="margin:0;">TRANSACTION LOGS</h1>
            <p class="sub-text">Record of AI Decisions & Outcomes</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    data = [
        {"Date": "2023-12-14 09:00", "Pair": "BTC/USDT", "Type": "LONG", "Entry": 42100, "Exit": 43500, "Result": "WIN", "PnL": "+$1,400"},
        {"Date": "2023-12-13 14:30", "Pair": "SOL/USDT", "Type": "SHORT", "Entry": 75.50, "Exit": 76.20, "Result": "LOSS", "PnL": "-$70"},
    ]
    df = pd.DataFrame(data)
    
    st.markdown('<div class="aq-card">', unsafe_allow_html=True)
    st.table(df)
    st.markdown('</div>', unsafe_allow_html=True)

if BACKEND_READY:
    render_navbar()
    if st.session_state.page == 'home':
        page_home()
    elif st.session_state.page == 'workspace':
        page_workspace()
    elif st.session_state.page == 'history':
        page_history()
else:
    st.warning("Backend modules are missing. System functionality is limited.")