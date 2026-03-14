"""
Stock Day Trading Analyzer — Streamlit Mobile App
Run locally:   streamlit run app.py
Deploy free:   https://share.streamlit.io
"""

import sys
import time
import json
import os
import warnings
warnings.filterwarnings("ignore")

import streamlit as st
import pandas as pd

# Import core logic from stock_analyzer (the if __name__ guard makes this safe)
sys.path.insert(0, os.path.dirname(__file__))
import stock_analyzer as sa

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Stock Analyzer",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Mobile-friendly CSS ───────────────────────────────────────────────────────
st.markdown("""
<style>
/* Bigger tap targets */
.stButton > button {
    width: 100%;
    font-size: 1.1rem;
    padding: 0.65rem 1rem;
    border-radius: 10px;
    font-weight: 600;
}
/* Tighter padding on mobile */
@media (max-width: 640px) {
    .block-container { padding: 0.75rem !important; }
    .stMetric { padding: 0.4rem !important; }
}
/* Tier badge pills */
.tier-a { background:#1a7a3f; color:white; padding:3px 10px; border-radius:20px; font-weight:700; }
.tier-b { background:#2d6a1a; color:white; padding:3px 10px; border-radius:20px; font-weight:700; }
.tier-c { background:#8a6a00; color:white; padding:3px 10px; border-radius:20px; font-weight:700; }
.tier-d { background:#7a1a1a; color:white; padding:3px 10px; border-radius:20px; font-weight:700; }
/* Score bar */
.score-bar-wrap { background:#333; border-radius:8px; height:10px; width:100%; margin-top:4px; }
.score-bar-fill { background:linear-gradient(90deg,#e05,#fa0,#0c6); border-radius:8px; height:10px; }
/* Expander header styling */
.stExpander { border-radius:12px !important; margin-bottom:6px; }
</style>
""", unsafe_allow_html=True)


# ── Session state defaults ────────────────────────────────────────────────────
if "watchlist" not in st.session_state:
    st.session_state.watchlist = sa.load_watchlist()
if "results" not in st.session_state:
    st.session_state.results = []
if "last_run" not in st.session_state:
    st.session_state.last_run = None


# ── Sidebar — watchlist management ───────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Settings")

    st.subheader("📋 Watchlist")
    add_input = st.text_input("Add tickers (comma-separated)", placeholder="e.g. HOOD, GME, RIVN")
    if st.button("➕ Add") and add_input:
        new = [t.strip().upper() for t in add_input.split(",") if t.strip()]
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
    st.subheader("🔧 Options")
    min_score  = st.slider("Min score to show", 0, 90, 0, step=5)
    skip_pm    = st.checkbox("Skip pre-market data (faster)")
    alert_score = st.slider("Alert me when score ≥", 0, 100, 70, step=5)

    st.divider()
    st.subheader("⏱️ Auto-Refresh")
    auto_on      = st.checkbox("Enable auto-refresh")
    refresh_mins = st.number_input("Refresh every (minutes)", 1, 60, 5, step=1,
                                   disabled=not auto_on)

    st.divider()
    st.caption(f"Watchlist: {len(st.session_state.watchlist)} stocks")
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

if run_clicked or (auto_on and st.session_state.results == []):
    symbols = st.session_state.watchlist
    results = []

    prog_bar = st.progress(0, text="Fetching stock data…")
    for i, sym in enumerate(symbols):
        prog_bar.progress((i + 1) / len(symbols), text=f"Analyzing {sym}…")
        data = sa.analyze_ticker(sym, fetch_premarket=not skip_pm)
        if data:
            results.append(data)

    prog_bar.empty()

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
    # ── Tier summary pills ──
    counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    for r in results:
        counts[sa.tier(r["score"])[0]] += 1

    c1, c2, c3, c4 = st.columns(4)
    for col, (ltr, color, label) in zip(
        [c1, c2, c3, c4],
        [("A","#1a7a3f","STRONG"), ("B","#2d6a1a","GOOD"),
         ("C","#8a6a00","WEAK"),   ("D","#7a1a1a","SKIP")]
    ):
        col.metric(f"**{ltr} — {label}**", counts[ltr])

    # ── Alerts ──
    alerts = [r for r in results if r["score"] >= alert_score]
    if alerts:
        syms = "  🔥  ".join(r["symbol"] for r in alerts)
        st.error(f"🚨 **ALERT** — Score ≥ {alert_score}:   {syms}")

    st.divider()

    # ── Stock cards ──
    tier_colors = {"A": "tier-a", "B": "tier-b", "C": "tier-c", "D": "tier-d"}

    for r in results:
        t     = sa.tier(r["score"])
        t_cls = tier_colors.get(t[0], "tier-d")
        pm    = r.get("pm_change_pct")
        pm_str = f"  |  PM {pm:+.1f}%" if pm is not None else ""
        alert_flag = "  🚨" if r["score"] >= alert_score else ""

        header = (
            f"**{r['symbol']}**  —  "
            f"<span class='{t_cls}'>{t}</span>"
            f"  •  Score: **{r['score']}**"
            f"  •  ${r['price']:.2f}"
            f"{pm_str}{alert_flag}"
        )

        company = r.get("company_name", r["symbol"])
        yahoo_url = f"https://finance.yahoo.com/quote/{r['symbol']}"
        sec_url   = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={r['symbol']}&type=&dateb=&owner=include&count=10&search_text="

        with st.expander(
            f"{r['symbol']}  |  {company}  |  Score {r['score']}  |  {t}  |  ${r['price']:.2f}{pm_str}{alert_flag}",
            expanded=(r["score"] >= 75)
        ):
            # Company name + links
            st.markdown(
                f"### {r['symbol']} — {company}\n"
                f"[📊 Yahoo Finance]({yahoo_url})   |   [📄 SEC Filings]({sec_url})"
            )

            # Score bar
            bar_w = r["score"]
            bar_color = "#1a7a3f" if r["score"] >= 75 else ("#8a6a00" if r["score"] >= 35 else "#7a1a1a")
            st.markdown(
                f'<div class="score-bar-wrap"><div class="score-bar-fill" '
                f'style="width:{bar_w}%;background:{bar_color};"></div></div>',
                unsafe_allow_html=True
            )
            st.caption(f"Score: {r['score']} / 100")

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Price",       f"${r['price']:.2f}")
                st.metric("RSI",         r["rsi"])
                st.metric("ATR %",       f"{r['atr_pct']:.1f}%")
            with col2:
                st.metric("Gap",         f"{r['gap_pct']:+.1f}%")
                st.metric("Volume ×avg", f"{r['volume_surge']:.2f}×")
                st.metric("EMA Trend",   r["ema_trend"])

            if pm is not None:
                pm_color = "normal" if pm >= 0 else "inverse"
                st.metric("Pre-Market",  f"{pm:+.1f}%", delta_color=pm_color)

            if r["reasons"]:
                st.markdown("**Signals:**")
                for reason in r["reasons"]:
                    st.markdown(f"• {reason}")

    # ── Full data table ──
    st.divider()
    with st.expander("📊 Full Data Table"):
        df = pd.DataFrame([{
            "Symbol":   r["symbol"],
            "Company":  r.get("company_name", r["symbol"]),
            "Score":    r["score"],
            "Tier":     sa.tier(r["score"]),
            "Price":    r["price"],
            "Gap %":    r["gap_pct"],
            "PM %":     r.get("pm_change_pct"),
            "RSI":      r["rsi"],
            "ATR %":    r["atr_pct"],
            "Vol ×avg": r["volume_surge"],
            "EMA":      r["ema_trend"],
        } for r in results])

        st.dataframe(
            df,
            use_container_width=True,
            column_config={
                "Score": st.column_config.ProgressColumn(
                    "Score", min_value=0, max_value=100, format="%d"
                ),
                "Gap %": st.column_config.NumberColumn(format="%.1f%%"),
                "PM %":  st.column_config.NumberColumn(format="%.1f%%"),
                "ATR %": st.column_config.NumberColumn(format="%.1f%%"),
            },
            hide_index=True,
        )

        # Download button
        csv = df.to_csv(index=False)
        st.download_button(
            "⬇️ Download CSV",
            csv,
            file_name="stock_analysis.csv",
            mime="text/csv",
        )

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
