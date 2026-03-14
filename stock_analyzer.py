"""
Stock Day Trading Candidate Analyzer v2
- Technical indicator scoring (RSI, MACD, ATR, Volume, EMA, Gap)
- Pre-market price & volume detection
- Custom watchlist (saved to watchlist.json)
- Auto-refresh / watch mode
- Score-based alerts
"""

import sys
import time
import json
import os
import warnings
warnings.filterwarnings("ignore")

try:
    import yfinance as yf
    import pandas as pd
    import numpy as np
except ImportError:
    print("Missing packages. Run: pip install yfinance pandas numpy rich")
    sys.exit(1)

try:
    from rich.console import Console
    from rich.table import Table
    from rich.progress import track
    from rich.panel import Panel
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

console = Console() if HAS_RICH else None

WATCHLIST_FILE = os.path.join(os.path.dirname(__file__), "watchlist.json")

DEFAULT_WATCHLIST = [
    "AAPL", "MSFT", "NVDA", "TSLA", "META", "GOOGL", "AMZN",
    "AMD", "PLTR", "SOFI", "MARA", "RIOT", "COIN",
    "SPY", "QQQ", "SQQQ", "TQQQ",
]


# ── Watchlist management ──────────────────────────────────────────────────────

def load_watchlist() -> list[str]:
    if os.path.exists(WATCHLIST_FILE):
        with open(WATCHLIST_FILE) as f:
            data = json.load(f)
            return data.get("symbols", DEFAULT_WATCHLIST)
    return DEFAULT_WATCHLIST.copy()


def save_watchlist(symbols: list[str]):
    with open(WATCHLIST_FILE, "w") as f:
        json.dump({"symbols": symbols}, f, indent=2)


# ── Technical indicators ──────────────────────────────────────────────────────

def calc_rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 1)


def calc_macd(series: pd.Series):
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return float(macd.iloc[-1]), float(signal.iloc[-1]), float((macd - signal).iloc[-1])


def calc_atr(high, low, close, period: int = 14) -> float:
    prev_close = close.shift(1)
    tr = pd.concat([high - low,
                    (high - prev_close).abs(),
                    (low - prev_close).abs()], axis=1).max(axis=1)
    return round(float(tr.rolling(period).mean().iloc[-1]), 4)


def calc_atr_pct(atr: float, price: float) -> float:
    return round((atr / price) * 100, 2) if price else 0


def volume_surge(volume: pd.Series, lookback: int = 20) -> float:
    avg = volume.iloc[-lookback - 1:-1].mean()
    today = volume.iloc[-1]
    return round(today / avg, 2) if avg else 0


def ema_crossover(close: pd.Series):
    ema9  = float(close.ewm(span=9,  adjust=False).mean().iloc[-1])
    ema21 = float(close.ewm(span=21, adjust=False).mean().iloc[-1])
    price = float(close.iloc[-1])
    gap_pct = round(((ema9 - ema21) / price) * 100, 2)
    if ema9 > ema21:   return "BULLISH", gap_pct
    elif ema9 < ema21: return "BEARISH", gap_pct
    return "NEUTRAL", gap_pct


def gap_pct(open_price: float, prev_close: float) -> float:
    if prev_close == 0: return 0
    return round(((open_price - prev_close) / prev_close) * 100, 2)


# ── Pre-market data ───────────────────────────────────────────────────────────

def get_premarket(ticker: yf.Ticker, last_close: float) -> dict:
    """
    Fetch pre/post-market price and volume.
    Returns dict with pm_price, pm_change_pct, pm_volume.
    """
    result = {"pm_price": None, "pm_change_pct": None, "pm_volume": 0}
    try:
        hist_pm = ticker.history(period="1d", interval="1m", prepost=True)
        if hist_pm.empty:
            return result

        # Pre-market rows have index before 09:30 Eastern
        # yfinance returns UTC; 09:30 ET = 14:30 UTC
        import datetime
        now_utc = pd.Timestamp.now(tz="UTC")
        market_open_utc = now_utc.replace(hour=14, minute=30, second=0, microsecond=0)

        pre = hist_pm[hist_pm.index < market_open_utc]
        if pre.empty:
            # Market may be open — use first bar of today
            pre = hist_pm.iloc[:30]

        if not pre.empty:
            pm_price  = float(pre["Close"].iloc[-1])
            pm_volume = int(pre["Volume"].sum())
            pm_change = round(((pm_price - last_close) / last_close) * 100, 2) if last_close else 0
            result.update(pm_price=round(pm_price, 2),
                          pm_change_pct=pm_change,
                          pm_volume=pm_volume)
    except Exception:
        pass
    return result


# ── Scoring ───────────────────────────────────────────────────────────────────

def score_stock(metrics: dict) -> tuple[int, list[str]]:
    score = 0
    reasons = []

    # Volume surge (0–25)
    vs = metrics["volume_surge"]
    if vs >= 3.0:   score += 25; reasons.append(f"Volume {vs:.1f}x avg  HUGE surge")
    elif vs >= 2.0: score += 18; reasons.append(f"Volume {vs:.1f}x avg  strong surge")
    elif vs >= 1.5: score += 10; reasons.append(f"Volume {vs:.1f}x avg  moderate surge")
    elif vs >= 1.0: score += 4

    # ATR% (0–25)
    atr_p = metrics["atr_pct"]
    if atr_p >= 4.0:   score += 25; reasons.append(f"ATR {atr_p:.1f}%  very high volatility")
    elif atr_p >= 2.5: score += 18; reasons.append(f"ATR {atr_p:.1f}%  high volatility")
    elif atr_p >= 1.5: score += 10; reasons.append(f"ATR {atr_p:.1f}%  moderate volatility")
    elif atr_p >= 0.8: score += 4

    # RSI (0–20)
    rsi = metrics["rsi"]
    if rsi > 70:        score += 15; reasons.append(f"RSI {rsi}  overbought momentum")
    elif rsi < 30:      score += 20; reasons.append(f"RSI {rsi}  oversold bounce candidate")
    elif 45 <= rsi <= 55: score += 8
    else:               score += 5

    # MACD histogram (0–15)
    if metrics["macd_hist"] > 0:
        score += 10; reasons.append("MACD bullish crossover")
    else:
        score += 3

    # Gap (0–15)
    gap = metrics["gap_pct"]
    if abs(gap) >= 3.0:   score += 15; reasons.append(f"Gap {gap:+.1f}%  catalyst present")
    elif abs(gap) >= 1.5: score += 8;  reasons.append(f"Gap {gap:+.1f}%  notable gap")
    elif abs(gap) >= 0.5: score += 4

    # Pre-market move bonus (0–10)
    pm_chg = metrics.get("pm_change_pct")
    if pm_chg is not None:
        if abs(pm_chg) >= 3.0:
            score += 10; reasons.append(f"Pre-market {pm_chg:+.1f}%  big PM move")
        elif abs(pm_chg) >= 1.5:
            score += 5;  reasons.append(f"Pre-market {pm_chg:+.1f}%  notable PM move")

    # EMA trend (0–10)
    trend = metrics["ema_trend"]
    if trend == "BULLISH":   score += 10; reasons.append("EMA 9 > 21  uptrend")
    elif trend == "BEARISH": score += 6;  reasons.append("EMA 9 < 21  downtrend / short bias")

    return min(score, 100), reasons


# ── Fetch & analyze ───────────────────────────────────────────────────────────

def analyze_ticker(symbol: str, fetch_premarket: bool = True) -> dict | None:
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="3mo", interval="1d")

        if hist.empty or len(hist) < 30:
            return None

        close  = hist["Close"]
        high   = hist["High"]
        low    = hist["Low"]
        volume = hist["Volume"]
        price  = float(close.iloc[-1])
        open_  = float(hist["Open"].iloc[-1])
        prev_close = float(close.iloc[-2])

        atr    = calc_atr(high, low, close)
        atr_p  = calc_atr_pct(atr, price)
        rsi    = calc_rsi(close)
        _, _, macd_hist = calc_macd(close)
        vs     = volume_surge(volume)
        trend, ema_gap = ema_crossover(close)
        gap    = gap_pct(open_, prev_close)

        pm_data = get_premarket(ticker, prev_close) if fetch_premarket else {}

        metrics = {
            "symbol":        symbol,
            "price":         round(price, 2),
            "gap_pct":       gap,
            "rsi":           rsi,
            "macd_hist":     round(macd_hist, 4),
            "atr":           atr,
            "atr_pct":       atr_p,
            "volume_surge":  vs,
            "ema_trend":     trend,
            "ema_gap_pct":   ema_gap,
            **pm_data,
        }

        score, reasons = score_stock(metrics)
        metrics["score"]   = score
        metrics["reasons"] = reasons
        return metrics

    except Exception as e:
        print(f"  [!] {symbol}: {e}")
        return None


# ── Display ───────────────────────────────────────────────────────────────────

def tier(score: int) -> str:
    if score >= 75: return "A  STRONG"
    if score >= 55: return "B  GOOD"
    if score >= 35: return "C  WEAK"
    return                  "D  SKIP"


def display_results(results: list[dict], alert_score: int = 0):
    results.sort(key=lambda x: x["score"], reverse=True)

    if HAS_RICH:
        _rich_table(results, alert_score)
    else:
        _plain_table(results)


def _rich_table(results, alert_score):
    table = Table(
        title="[bold cyan]Day Trading Candidate Analysis[/bold cyan]",
        box=box.ROUNDED, show_lines=True,
        header_style="bold white on dark_blue",
    )
    table.add_column("#",         justify="center", width=3)
    table.add_column("Symbol",    style="bold cyan", width=6)
    table.add_column("Price",     justify="right",  width=8)
    table.add_column("Score",     justify="center", width=6)
    table.add_column("Tier",      width=10)
    table.add_column("Gap%",      justify="right",  width=6)
    table.add_column("PM%",       justify="right",  width=6)
    table.add_column("RSI",       justify="right",  width=5)
    table.add_column("ATR%",      justify="right",  width=6)
    table.add_column("Vol x",     justify="right",  width=6)
    table.add_column("EMA",       width=8)
    table.add_column("Top Signal", width=38)

    tier_colors = {"A": "bold green", "B": "green", "C": "yellow", "D": "red"}

    for i, m in enumerate(results, 1):
        t      = tier(m["score"])
        color  = tier_colors.get(t[0], "white")
        gap_c  = "green" if m["gap_pct"] > 0 else ("red" if m["gap_pct"] < 0 else "white")
        pm_chg = m.get("pm_change_pct")
        pm_str = f"{pm_chg:+.1f}%" if pm_chg is not None else "—"
        pm_c   = "green" if (pm_chg or 0) > 0 else ("red" if (pm_chg or 0) < 0 else "white")
        ema_c  = "green" if m["ema_trend"] == "BULLISH" else ("red" if m["ema_trend"] == "BEARISH" else "white")
        top    = m["reasons"][0] if m["reasons"] else "—"
        alert  = " [blink bold red]ALERT[/blink bold red]" if m["score"] >= alert_score > 0 else ""

        table.add_row(
            str(i),
            m["symbol"] + alert,
            f"${m['price']:.2f}",
            f"[{color}]{m['score']}[/{color}]",
            f"[{color}]{t}[/{color}]",
            f"[{gap_c}]{m['gap_pct']:+.1f}%[/{gap_c}]",
            f"[{pm_c}]{pm_str}[/{pm_c}]",
            str(m["rsi"]),
            f"{m['atr_pct']:.1f}%",
            f"{m['volume_surge']:.2f}x",
            f"[{ema_c}]{m['ema_trend']}[/{ema_c}]",
            top,
        )

    console.print()
    console.print(table)

    # Detail cards for top 3
    top3 = [m for m in results[:3] if m["score"] >= 35]
    if top3:
        console.print("\n[bold underline]Top Candidate Details:[/bold underline]")
        for m in top3:
            pm_chg = m.get("pm_change_pct")
            pm_str = f"  PM: {pm_chg:+.1f}%" if pm_chg is not None else ""
            console.print(
                f"\n[bold cyan]{m['symbol']}[/bold cyan]"
                f" — Score [bold]{m['score']}[/bold]"
                f" | ${m['price']:.2f}{pm_str}"
            )
            for r in m["reasons"]:
                console.print(f"  • {r}")


def _plain_table(results):
    print("\n" + "=" * 90)
    print("  DAY TRADING CANDIDATE ANALYSIS")
    print("=" * 90)
    hdr = (f"{'#':>3}  {'SYM':<6}  {'PRICE':>8}  {'SCORE':>5}  {'TIER':<10}"
           f"  {'GAP':>6}  {'PM%':>6}  {'RSI':>5}  {'ATR%':>5}  {'VOL':>6}  TREND")
    print(hdr)
    print("-" * 90)
    for i, m in enumerate(results, 1):
        t = tier(m["score"])
        pm_chg = m.get("pm_change_pct")
        pm_str = f"{pm_chg:+.1f}%" if pm_chg is not None else "  —"
        print(
            f"{i:>3}  {m['symbol']:<6}  ${m['price']:>7.2f}  {m['score']:>5}  {t:<10}"
            f"  {m['gap_pct']:>+5.1f}%  {pm_str:>6}  {m['rsi']:>5}"
            f"  {m['atr_pct']:>4.1f}%  {m['volume_surge']:>5.2f}x  {m['ema_trend']}"
        )
    print("=" * 90)


# ── Watch mode ────────────────────────────────────────────────────────────────

def watch_mode(watchlist: list[str], interval_min: int, alert_score: int, min_score: int):
    if HAS_RICH:
        console.print(Panel(
            f"[bold green]WATCH MODE[/bold green]  —  refreshing every [cyan]{interval_min}[/cyan] min"
            f"  |  alert threshold: [yellow]{alert_score}[/yellow]"
            f"  |  Ctrl+C to stop",
            box=box.ROUNDED
        ))
    else:
        print(f"\nWATCH MODE — refreshing every {interval_min} min | Ctrl+C to stop\n")

    while True:
        import datetime
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if HAS_RICH:
            console.rule(f"[dim]Run at {now}[/dim]")
            iterator = track(watchlist, description="Fetching...")
        else:
            print(f"\n--- {now} ---")
            iterator = watchlist

        results = []
        for sym in iterator:
            data = analyze_ticker(sym)
            if data:
                results.append(data)

        if min_score:
            results = [r for r in results if r["score"] >= min_score]

        if results:
            display_results(results, alert_score)
            # Print alerts to console
            alerts = [r for r in results if alert_score > 0 and r["score"] >= alert_score]
            if alerts and HAS_RICH:
                syms = ", ".join(r["symbol"] for r in alerts)
                console.print(Panel(
                    f"[bold red]ALERT:[/bold red] [bold]{syms}[/bold] scored >= {alert_score}",
                    style="red", box=box.HEAVY
                ))
        else:
            print("No results meet the minimum score.")

        if HAS_RICH:
            console.print(f"\n[dim]Next refresh in {interval_min} minute(s)...[/dim]")
        else:
            print(f"\nNext refresh in {interval_min} minute(s)...")

        time.sleep(interval_min * 60)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Stock day-trading candidate analyzer",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # Watchlist management
    wl_group = parser.add_argument_group("Watchlist")
    wl_group.add_argument("symbols", nargs="*",
        help="Tickers to analyze. Omit to use saved watchlist.")
    wl_group.add_argument("--add", nargs="+", metavar="TICKER",
        help="Add tickers to your saved watchlist.")
    wl_group.add_argument("--remove", nargs="+", metavar="TICKER",
        help="Remove tickers from your saved watchlist.")
    wl_group.add_argument("--list-watchlist", action="store_true",
        help="Show your saved watchlist and exit.")
    wl_group.add_argument("--reset-watchlist", action="store_true",
        help="Reset watchlist to defaults.")

    # Filters
    filt_group = parser.add_argument_group("Filters")
    filt_group.add_argument("--min-score", type=int, default=0,
        help="Only show stocks >= this score (0-100).")
    filt_group.add_argument("--no-premarket", action="store_true",
        help="Skip pre-market data fetch (faster).")

    # Watch mode
    watch_group = parser.add_argument_group("Watch / Alert Mode")
    watch_group.add_argument("--watch", type=int, metavar="MINUTES", default=0,
        help="Auto-refresh every N minutes (e.g. --watch 5).")
    watch_group.add_argument("--alert", type=int, default=0, metavar="SCORE",
        help="Highlight stocks that score >= SCORE (e.g. --alert 70).")

    args = parser.parse_args()

    # ── Watchlist edits ──
    watchlist = load_watchlist()

    if args.reset_watchlist:
        save_watchlist(DEFAULT_WATCHLIST.copy())
        print("Watchlist reset to defaults.")
        return

    if args.add:
        new = [s.upper() for s in args.add if s.upper() not in watchlist]
        watchlist.extend(new)
        save_watchlist(watchlist)
        print(f"Added: {', '.join(new)}. Watchlist: {', '.join(watchlist)}")
        return

    if args.remove:
        rem = [s.upper() for s in args.remove]
        watchlist = [s for s in watchlist if s not in rem]
        save_watchlist(watchlist)
        print(f"Removed: {', '.join(rem)}. Watchlist: {', '.join(watchlist)}")
        return

    if args.list_watchlist:
        print("Current watchlist:")
        for s in watchlist:
            print(f"  {s}")
        return

    # ── Choose symbols ──
    symbols = [s.upper() for s in args.symbols] if args.symbols else watchlist
    fetch_pm = not args.no_premarket

    # ── Watch mode ──
    if args.watch:
        watch_mode(symbols, args.watch, args.alert, args.min_score)
        return

    # ── Single run ──
    if HAS_RICH:
        console.print(f"\n[bold]Analyzing [cyan]{len(symbols)}[/cyan] stocks"
                      f"{'  (+ pre-market data)' if fetch_pm else ''}...[/bold]")
        iterator = track(symbols, description="Fetching data...")
    else:
        print(f"\nAnalyzing {len(symbols)} stocks...")
        iterator = symbols

    results = []
    for sym in iterator:
        data = analyze_ticker(sym, fetch_premarket=fetch_pm)
        if data:
            results.append(data)

    if not results:
        print("No results. Check ticker symbols or internet connection.")
        sys.exit(1)

    if args.min_score:
        results = [r for r in results if r["score"] >= args.min_score]

    if not results:
        print(f"No stocks scored >= {args.min_score}.")
        sys.exit(0)

    display_results(results, args.alert)

    print("\nSCORING GUIDE:")
    print("  75-100  A STRONG  Multiple strong signals, high priority")
    print("  55-74   B GOOD    Decent setup, worth watching")
    print("  35-54   C WEAK    Marginal signals only")
    print("  0-34    D SKIP    Little day trading appeal today")
    print("\nUSAGE EXAMPLES:")
    print("  python stock_analyzer.py                        # run default watchlist")
    print("  python stock_analyzer.py AAPL TSLA NVDA         # specific tickers")
    print("  python stock_analyzer.py --watch 5              # refresh every 5 min")
    print("  python stock_analyzer.py --watch 10 --alert 70  # alert on score >= 70")
    print("  python stock_analyzer.py --add HOOD RIVN        # add to watchlist")
    print("  python stock_analyzer.py --remove SPY QQQ       # remove from watchlist")
    print("  python stock_analyzer.py --min-score 55         # only show B or better")
    print("  python stock_analyzer.py --no-premarket         # faster, skip PM data")
    print("\nDISCLAIMER: For educational/research purposes only. Not financial advice.")


if __name__ == "__main__":
    main()
