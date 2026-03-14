"""
Stock Day Trading Analyzer — Streamlit Mobile App
Run locally:   streamlit run app.py
Deploy free:   https://share.streamlit.io
"""

import sys
import time
import os
import warnings
warnings.filterwarnings("ignore")

import streamlit as st
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import stock_analyzer as sa

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Stock Analyzer",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Dark theme + color scheme ─────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Base dark background ── */
.stApp, .main, section[data-testid="stSidebar"] {
    background-color: #0d1117;
}
.block-container {
    background-color: #0d1117;
    padding-top: 1.5rem;
}

/* ── Run button ── */
.stButton > button {
    width: 100%;
    font-size: 1.15rem;
    padding: 0.75rem 1rem;
    border-radius: 12px;
    font-weight: 700;
    background: linear-gradient(135deg, #00c6a7, #0077cc);
    color: white;
    border: none;
    letter-spacing: 0.03em;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #00e0bb, #0099ff);
    transform: translateY(-1px);
}

/* ── Tier badge pills ── */
.tier-a { background:#00c6a7; color:#000; padding:3px 12px; border-radius:20px; font-weight:800; }
.tier-b { background:#0077cc; color:#fff; padding:3px 12px; border-radius:20px; font-weight:800; }
.tier-c { background:#e07b00; color:#fff; padding:3px 12px; border-radius:20px; font-weight:800; }
.tier-d { background:#aa2222; color:#fff; padding:3px 12px; border-radius:20px; font-weight:800; }

/* ── Score bar ── */
.score-bar-wrap { background:#1e2a3a; border-radius:8px; height:12px; width:100%; margin:6px 0; }
.score-bar-fill { border-radius:8px; height:12px; }

/* ── Trade level boxes ── */
.trade-box {
    border-radius: 12px;
    padding: 10px 14px;
    margin: 4px 0;
    font-size: 1rem;
    font-weight: 600;
}
.trade-entry    { background:#0d2b1e; border:1px solid #00c6a7; color:#00e0bb; }
.trade-stop     { background:#2b0d0d; border:1px solid #cc2222; color:#ff5555; }
.trade-target1  { background:#1a1a00; border:1px solid #ccaa00; color:#ffd700; }
.trade-target2  { background:#1a2400; border:1px solid #88cc00; color:#aaff44; }

/* ── Expander card ── */
.stExpander {
    border-radius: 14px !important;
    margin-bottom: 8px !important;
    border: 1px solid #1e2a3a !important;
    background-color: #111827 !important;
}

/* ── Mobile padding ── */
@media (max-width: 640px) {
    .block-container { padding: 0.5rem !important; }
}
</style>
""", unsafe_allow_html=True)


# ── Session state ─────────────────────────────────────────────────────────────
if "watchlist" not in st.session_state:
    st.session_state.watchlist = sa.load_watchlist()
if "results"   not in st.session_state:
    st.session_state.results = []
if "last_run"  not in st.session_state:
    st.session_state.last_run = None


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Settings")

    st.markdown("### 📋 Watchlist")
    add_input = st.text_input("Add tickers (comma-separated)", placeholder="e.g. HOOD, GME, RIVN")
    if st.button("➕ Add") and add_input:
        new   = [t.strip().upper() for t in add_input.split(",") if t.strip()]
        added = [t for t in new if t not in st.session_state.watchlist]
        st.session_state.watchlist.extend(added)
        sa.save_watchlist(st.session_state.watchlist)
        st.success(f"Added: {', '.join(added)}" if added else "Already in watchlist")
        st.rerun()

    to_remove = st.multiselect("Remove tickers", st.session_state.watchlist)
    if st.button("➖ Remove selected") and to_remove:
        st.session_state.watchlist = [t for t in st.session_state.watchlist if t not in to_remove]
        sa.save_watchlist(st.session_state.watchlist)
        st.rerun()

    if st.button("🔄 Reset to defaults"):
        st.session_state.watchlist = sa.DEFAULT_WATCHLIST.copy()
        sa.save_watchlist(st.session_state.watchlist)
        st.rerun()

    st.divider()
    st.markdown("### 🔧 Options")
    min_score   = st.slider("Min score to show", 0, 90, 0, step=5)
    skip_pm     = st.checkbox("Skip pre-market data (faster)")
    alert_score = st.slider("Alert me when score ≥", 0, 100, 70, step=5)

    st.divider()
    st.markdown("### ⏱️ Auto-Refresh")
    auto_on      = st.checkbox("Enable auto-refresh")
    refresh_mins = st.number_input("Refresh every (minutes)", 1, 60, 5,
                                   disabled=not auto_on)

    st.divider()
    st.caption(f"Watching {len(st.session_state.watchlist)} stocks")
    st.caption("⚠️ Not financial advice.")


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("## 📈 Day Trading Analyzer")
wl_preview = "  ·  ".join(st.session_state.watchlist[:8])
extra = f"  +{len(st.session_state.watchlist)-8} more" if len(st.session_state.watchlist) > 8 else ""
st.caption(f"Watching: {wl_preview}{extra}")
if st.session_state.last_run:
    st.caption(f"Last run: {st.session_state.last_run}")


# ── Run button ────────────────────────────────────────────────────────────────
run_clicked = st.button("🚀 Run Analysis", type="primary", use_container_width=True)

if run_clicked or (auto_on and not st.session_state.results):
    results = []
    prog = st.progress(0, text="Fetching stock data…")
    for i, sym in enumerate(st.session_state.watchlist):
        prog.progress((i + 1) / len(st.session_state.watchlist), text=f"Analyzing {sym}…")
        data = sa.analyze_ticker(sym, fetch_premarket=not skip_pm)
        if data:
            results.append(data)
    prog.empty()

    if min_score:
        results = [r for r in results if r["score"] >= min_score]
    results.sort(key=lambda x: x["score"], reverse=True)
    st.session_state.results = results

    import datetime
    st.session_state.last_run = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.rerun()


# ── Results ───────────────────────────────────────────────────────────────────
results = st.session_state.results

if results:
    # Tier summary
    counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    for r in results:
        counts[sa.tier(r["score"])[0]] += 1

    c1, c2, c3, c4 = st.columns(4)
    for col, (ltr, label) in zip(
        [c1, c2, c3, c4],
        [("A","STRONG"), ("B","GOOD"), ("C","WEAK"), ("D","SKIP")]
    ):
        col.metric(f"{ltr} — {label}", counts[ltr])

    # Alerts
    alerts = [r for r in results if r["score"] >= alert_score]
    if alerts:
        syms = "  🔥  ".join(r["symbol"] for r in alerts)
        st.error(f"🚨 **ALERT** — Score ≥ {alert_score}:   {syms}")

    st.divider()

    # ── Stock cards ──────────────────────────────────────────────────────────
    tier_colors = {"A": "tier-a", "B": "tier-b", "C": "tier-c", "D": "tier-d"}

    for r in results:
        t       = sa.tier(r["score"])
        t_cls   = tier_colors.get(t[0], "tier-d")
        pm      = r.get("pm_change_pct")
        pm_str  = f"  |  PM {pm:+.1f}%" if pm is not None else ""
        alert_f = "  🚨" if r["score"] >= alert_score else ""
        company = r.get("company_name", r["symbol"])

        yahoo_url = f"https://finance.yahoo.com/quote/{r['symbol']}"
        sec_url   = (f"https://www.sec.gov/cgi-bin/browse-edgar"
                     f"?action=getcompany&company={r['symbol']}"
                     f"&type=&dateb=&owner=include&count=10&search_text=")

        with st.expander(
            f"{r['symbol']}  |  {company}  |  Score {r['score']}  |  {t}  |  ${r['price']:.2f}{pm_str}{alert_f}",
            expanded=(r["score"] >= 75)
        ):
            # Company + links
            st.markdown(
                f"### {r['symbol']} — {company}\n"
                f"[📊 Yahoo Finance]({yahoo_url})   |   [📄 SEC Filings]({sec_url})"
            )

            # Score bar
            bar_color = "#00c6a7" if r["score"] >= 75 else ("#e07b00" if r["score"] >= 35 else "#aa2222")
            st.markdown(
                f'<div class="score-bar-wrap">'
                f'<div class="score-bar-fill" style="width:{r["score"]}%;background:{bar_color};"></div>'
                f'</div>',
                unsafe_allow_html=True
            )
            st.caption(f"Score: {r['score']} / 100")

            # ── Trade levels ──────────────────────────────────────────────
            direction = r.get("direction", "LONG  (Buy)")
            is_long   = "LONG" in direction

            st.markdown("---")
            st.markdown(f"**📐 Trade Setup — {direction}**")

            lbl_entry  = "🟢 Entry (Buy)"  if is_long else "🔴 Entry (Sell Short)"
            lbl_stop   = "🛑 Stop Loss"
            lbl_tp1    = "🎯 Take Profit 1"
            lbl_tp2    = "🎯 Take Profit 2"

            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown(
                    f'<div class="trade-box trade-entry">'
                    f'{lbl_entry}<br><b>${r["entry"]:.2f}</b></div>',
                    unsafe_allow_html=True
                )
                st.markdown(
                    f'<div class="trade-box trade-stop">'
                    f'{lbl_stop}<br><b>${r["stop_loss"]:.2f}</b>'
                    f'  <small>(−${r["risk_amt"]:.2f})</small></div>',
                    unsafe_allow_html=True
                )
            with col_b:
                st.markdown(
                    f'<div class="trade-box trade-target1">'
                    f'{lbl_tp1}<br><b>${r["take_profit1"]:.2f}</b>'
                    f'  <small>(+${abs(r["take_profit1"]-r["entry"]):.2f})</small></div>',
                    unsafe_allow_html=True
                )
                st.markdown(
                    f'<div class="trade-box trade-target2">'
                    f'{lbl_tp2}<br><b>${r["take_profit2"]:.2f}</b>'
                    f'  <small>(+${abs(r["take_profit2"]-r["entry"]):.2f})</small></div>',
                    unsafe_allow_html=True
                )
            st.caption("Based on 0.5× ATR stop, 1× and 2× ATR targets  |  Not financial advice")

            # ── Technical metrics ─────────────────────────────────────────
            st.markdown("---")
            st.markdown("**📊 Technicals**")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Price",        f"${r['price']:.2f}")
                st.metric("RSI",          r["rsi"])
                st.metric("ATR %",        f"{r['atr_pct']:.1f}%")
            with col2:
                st.metric("Gap",          f"{r['gap_pct']:+.1f}%")
                st.metric("Volume ×avg",  f"{r['volume_surge']:.2f}×")
                st.metric("EMA Trend",    r["ema_trend"])

            if pm is not None:
                st.metric("Pre-Market", f"{pm:+.1f}%",
                          delta_color="normal" if pm >= 0 else "inverse")

            if r["reasons"]:
                st.markdown("**Signals:**")
                for reason in r["reasons"]:
                    st.markdown(f"• {reason}")

    # ── Full data table ───────────────────────────────────────────────────────
    st.divider()
    with st.expander("📊 Full Data Table"):
        df = pd.DataFrame([{
            "Symbol":    r["symbol"],
            "Company":   r.get("company_name", r["symbol"]),
            "Score":     r["score"],
            "Tier":      sa.tier(r["score"]),
            "Price":     r["price"],
            "Direction": r.get("direction","—"),
            "Entry":     r.get("entry"),
            "Stop Loss": r.get("stop_loss"),
            "Target 1":  r.get("take_profit1"),
            "Target 2":  r.get("take_profit2"),
            "Gap %":     r["gap_pct"],
            "PM %":      r.get("pm_change_pct"),
            "RSI":       r["rsi"],
            "ATR %":     r["atr_pct"],
            "Vol ×avg":  r["volume_surge"],
            "EMA":       r["ema_trend"],
        } for r in results])

        st.dataframe(
            df,
            use_container_width=True,
            column_config={
                "Score": st.column_config.ProgressColumn(
                    "Score", min_value=0, max_value=100, format="%d"
                ),
                "Gap %":  st.column_config.NumberColumn(format="%.1f%%"),
                "PM %":   st.column_config.NumberColumn(format="%.1f%%"),
                "ATR %":  st.column_config.NumberColumn(format="%.1f%%"),
                "Entry":  st.column_config.NumberColumn(format="$%.2f"),
                "Stop Loss": st.column_config.NumberColumn(format="$%.2f"),
                "Target 1":  st.column_config.NumberColumn(format="$%.2f"),
                "Target 2":  st.column_config.NumberColumn(format="$%.2f"),
            },
            hide_index=True,
        )

        csv = df.to_csv(index=False)
        st.download_button("⬇️ Download CSV", csv,
                           file_name="stock_analysis.csv", mime="text/csv")

elif not run_clicked:
    st.info("👆 Tap **Run Analysis** to scan your watchlist.")


# ── Auto-refresh countdown ────────────────────────────────────────────────────
if auto_on and st.session_state.results:
    placeholder = st.empty()
    secs = int(refresh_mins * 60)
    for remaining in range(secs, 0, -1):
        mins, s = divmod(remaining, 60)
        placeholder.caption(f"⏱ Next refresh in {mins:02d}:{s:02d}")
        time.sleep(1)
    placeholder.caption("🔄 Refreshing now…")
    st.session_state.results = []
    st.rerun()
