"""
Paper Trading Tracker
- Loads trades from paper_trades.json
- Fetches current prices via yfinance
- Calculates P&L per trade and for the full portfolio
- Saves a daily snapshot and displays a summary

Usage:
  python paper_trades.py                    # update prices and show P&L
  python paper_trades.py --close MARA       # mark a trade closed at current price
  python paper_trades.py --history          # show full snapshot history
  python paper_trades.py --email            # send status email (uses env vars)

Email env vars required for --email:
  EMAIL_FROM      sender Gmail address
  EMAIL_PASSWORD  Gmail App Password
  EMAIL_TO        recipient address
"""

import sys
import json
import os
import argparse
import smtplib
import io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date

try:
    import yfinance as yf
except ImportError:
    print("Run: pip install yfinance")
    sys.exit(1)

try:
    from rich.console import Console
    from rich.table import Table
    from rich import box
    from rich.panel import Panel
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

TRADES_FILE = os.path.join(os.path.dirname(__file__), "paper_trades.json")
console = Console() if HAS_RICH else None


def load_trades() -> dict:
    with open(TRADES_FILE) as f:
        return json.load(f)


def save_trades(data: dict):
    with open(TRADES_FILE, "w") as f:
        json.dump(data, f, indent=2)


def fetch_price(symbol: str) -> float | None:
    try:
        hist = yf.Ticker(symbol).history(period="1d", interval="1d")
        if hist.empty:
            return None
        return round(float(hist["Close"].iloc[-1]), 2)
    except Exception:
        return None


def calc_pnl(trade: dict, current_price: float) -> tuple[float, float]:
    pnl = round((current_price - trade["entry_price"]) * trade["shares"], 2)
    pnl_pct = round(((current_price - trade["entry_price"]) / trade["entry_price"]) * 100, 2)
    if trade["direction"] == "SHORT":
        pnl = -pnl
        pnl_pct = -pnl_pct
    return pnl, pnl_pct


def status_tag(trade: dict, current_price: float) -> str:
    if trade["status"] == "CLOSED":
        return "CLOSED"
    sl = trade["stop_loss"]
    tp1 = trade["take_profit1"]
    tp2 = trade["take_profit2"]
    if trade["direction"] == "LONG":
        if current_price <= sl:
            return "STOP HIT"
        if current_price >= tp2:
            return "TP2 HIT"
        if current_price >= tp1:
            return "TP1 HIT"
    else:
        if current_price >= sl:
            return "STOP HIT"
        if current_price <= tp2:
            return "TP2 HIT"
        if current_price <= tp1:
            return "TP1 HIT"
    return "OPEN"


def update_and_display(close_symbol: str | None = None):
    data = load_trades()
    today = str(date.today())

    open_trades = [t for t in data["trades"] if t["status"] == "OPEN"]
    symbols = [t["symbol"] for t in open_trades]

    print(f"\nFetching prices for: {', '.join(symbols)}...")
    prices = {sym: fetch_price(sym) for sym in symbols}

    total_value = 0.0
    total_cost  = 0.0

    for trade in data["trades"]:
        if trade["status"] == "CLOSED":
            # Use last snapshot price for closed trades
            last = trade["snapshots"][-1]
            current_price = last["price"]
        else:
            current_price = prices.get(trade["symbol"])
            if current_price is None:
                print(f"  [!] Could not fetch price for {trade['symbol']}, skipping.")
                continue

        pnl, pnl_pct = calc_pnl(trade, current_price)
        tag = status_tag(trade, current_price)

        # Auto-close if stop or TP hit
        should_close = tag in ("STOP HIT", "TP2 HIT") and trade["status"] == "OPEN"
        # Sanity check: reject auto-close if price is >25% from entry (likely bad yfinance data)
        if should_close:
            move_pct = abs(current_price - trade["entry_price"]) / trade["entry_price"]
            if move_pct > 0.25:
                print(f"  [!] {trade['symbol']} flagged {tag} at ${current_price:.2f} "
                      f"({move_pct:.1%} from entry) — skipping auto-close, possible bad data")
                should_close = False
        # Manual close
        if close_symbol and trade["symbol"] == close_symbol.upper() and trade["status"] == "OPEN":
            should_close = True

        if should_close:
            trade["status"] = "CLOSED"
            sim = data["simulation"]
            sim["realized_pnl"] = round(sim.get("realized_pnl", 0.0) + pnl, 2)
            sim["cash_remaining"] = round(sim.get("cash_remaining", 0.0) + trade["allocation"] + pnl, 2)
            print(f"  >> {trade['symbol']} closed ({tag}) at ${current_price}, P&L: ${pnl:+.2f}")

        # Save snapshot (once per day)
        last_date = trade["snapshots"][-1]["date"] if trade["snapshots"] else None
        if last_date != today:
            trade["snapshots"].append({
                "date": today,
                "price": current_price,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
            })

        total_cost  += trade["allocation"]
        total_value += trade["allocation"] + pnl

    # Remove closed trades — realized P&L and cash already captured above
    data["trades"] = [t for t in data["trades"] if t["status"] != "CLOSED"]

    save_trades(data)
    _display(data, prices, today)
    return data, prices


def _display(data: dict, prices: dict, today: str):
    sim = data["simulation"]

    if HAS_RICH:
        table = Table(
            title=f"[bold cyan]Paper Portfolio — {today}[/bold cyan]",
            box=box.ROUNDED, show_lines=True,
            header_style="bold white on dark_blue",
        )
        table.add_column("Symbol",    style="bold cyan", width=7)
        table.add_column("Dir",       width=6)
        table.add_column("Entry $",   justify="right", width=9)
        table.add_column("Current $", justify="right", width=10)
        table.add_column("Shares",    justify="right", width=7)
        table.add_column("Alloc $",   justify="right", width=9)
        table.add_column("P&L $",     justify="right", width=9)
        table.add_column("P&L %",     justify="right", width=8)
        table.add_column("Stop",      justify="right", width=8)
        table.add_column("TP1",       justify="right", width=8)
        table.add_column("Status",    width=10)

        total_pnl = 0.0
        total_cost = 0.0

        for trade in data["trades"]:
            sym = trade["symbol"]
            cur = prices.get(sym) or trade["snapshots"][-1]["price"]
            pnl, pnl_pct = calc_pnl(trade, cur)
            tag = status_tag(trade, cur) if trade["status"] == "OPEN" else "CLOSED"

            pnl_color = "green" if pnl >= 0 else "red"
            tag_color = {
                "OPEN": "white", "CLOSED": "dim",
                "TP1 HIT": "green", "TP2 HIT": "bold green",
                "STOP HIT": "bold red",
            }.get(tag, "white")

            table.add_row(
                sym,
                trade["direction"],
                f"${trade['entry_price']:.2f}",
                f"${cur:.2f}",
                f"{trade['shares']:.3f}",
                f"${trade['allocation']:.2f}",
                f"[{pnl_color}]${pnl:+.2f}[/{pnl_color}]",
                f"[{pnl_color}]{pnl_pct:+.2f}%[/{pnl_color}]",
                f"${trade['stop_loss']:.2f}",
                f"${trade['take_profit1']:.2f}",
                f"[{tag_color}]{tag}[/{tag_color}]",
            )
            total_pnl  += pnl
            total_cost += trade["allocation"]

        console.print()
        console.print(table)

        realized  = sim.get("realized_pnl", 0.0)
        cash      = sim.get("cash_remaining", 0.0)
        net_pnl   = round(total_pnl + realized, 2)
        port_value = round(cash + total_cost + total_pnl, 2)
        total_pct = round((net_pnl / sim["total_budget"]) * 100, 2) if sim["total_budget"] else 0
        pnl_color = "green" if net_pnl >= 0 else "red"
        console.print(Panel(
            f"Budget: [bold]${sim['total_budget']:.2f}[/bold]  |  "
            f"Portfolio Value: [bold]${port_value:.2f}[/bold]  |  "
            f"Total P&L: [{pnl_color}][bold]${net_pnl:+.2f}  ({total_pct:+.2f}%)[/bold][/{pnl_color}]  |  "
            f"Period: {sim['start_date']} to {sim['end_date']}",
            box=box.ROUNDED
        ))
    else:
        print(f"\n{'='*80}")
        print(f"  PAPER PORTFOLIO  —  {today}")
        print(f"{'='*80}")
        print(f"  {'SYM':<6}  {'DIR':<6}  {'ENTRY':>8}  {'CUR':>8}  {'SHARES':>7}  "
              f"{'ALLOC':>8}  {'P&L $':>9}  {'P&L %':>7}  STATUS")
        print(f"  {'-'*76}")

        total_pnl = 0.0
        total_cost = 0.0

        for trade in data["trades"]:
            sym = trade["symbol"]
            cur = prices.get(sym) or trade["snapshots"][-1]["price"]
            pnl, pnl_pct = calc_pnl(trade, cur)
            tag = status_tag(trade, cur) if trade["status"] == "OPEN" else "CLOSED"
            print(f"  {sym:<6}  {trade['direction']:<6}  ${trade['entry_price']:>7.2f}  "
                  f"${cur:>7.2f}  {trade['shares']:>7.3f}  ${trade['allocation']:>7.2f}  "
                  f"${pnl:>+8.2f}  {pnl_pct:>+6.2f}%  {tag}")
            total_pnl  += pnl
            total_cost += trade["allocation"]

        realized   = sim.get("realized_pnl", 0.0)
        cash       = sim.get("cash_remaining", 0.0)
        net_pnl    = round(total_pnl + realized, 2)
        port_value = round(cash + total_cost + total_pnl, 2)
        total_pct  = round((net_pnl / sim["total_budget"]) * 100, 2) if sim["total_budget"] else 0
        print(f"\n  Budget: ${sim['total_budget']:.2f}  |  "
              f"Portfolio Value: ${port_value:.2f}  |  "
              f"Total P&L: ${net_pnl:+.2f} ({total_pct:+.2f}%)")
        print(f"  Period: {sim['start_date']} → {sim['end_date']}")
        print(f"{'='*80}")


def show_history():
    data = load_trades()
    for trade in data["trades"]:
        print(f"\n{trade['symbol']} ({trade['status']}) - entry ${trade['entry_price']}")
        print(f"  {'Date':<12}  {'Price':>8}  {'P&L $':>9}  {'P&L %':>7}")
        for snap in trade["snapshots"]:
            print(f"  {snap['date']:<12}  ${snap['price']:>7.2f}  ${snap['pnl']:>+8.2f}  {snap['pnl_pct']:>+6.2f}%")


def build_email_body(data: dict, prices: dict, today: str) -> str:
    sim = data["simulation"]
    lines = [
        f"Paper Trading Status - {today}",
        f"Period: {sim['start_date']} to {sim['end_date']}",
        "=" * 70,
        f"  {'Symbol':<7} {'Dir':<6} {'Entry':>8} {'Current':>9} {'Shares':>7} {'Alloc':>8} {'P&L $':>9} {'P&L %':>8} {'Status':<10}",
        "-" * 70,
    ]

    total_pnl = 0.0
    total_cost = 0.0

    for trade in data["trades"]:
        sym = trade["symbol"]
        cur = prices.get(sym) or trade["snapshots"][-1]["price"]
        pnl, pnl_pct = calc_pnl(trade, cur)
        tag = status_tag(trade, cur) if trade["status"] == "OPEN" else "CLOSED"
        lines.append(
            f"  {sym:<7} {trade['direction']:<6} ${trade['entry_price']:>7.2f} "
            f"${cur:>8.2f} {trade['shares']:>7.3f} ${trade['allocation']:>7.2f} "
            f"${pnl:>+8.2f} {pnl_pct:>+7.2f}% {tag:<10}"
        )
        total_pnl  += pnl
        total_cost += trade["allocation"]

    realized   = sim.get("realized_pnl", 0.0)
    cash       = sim.get("cash_remaining", 0.0)
    net_pnl    = round(total_pnl + realized, 2)
    port_value = round(cash + total_cost + total_pnl, 2)
    total_pct  = round((net_pnl / sim["total_budget"]) * 100, 2) if sim["total_budget"] else 0
    lines += [
        "=" * 70,
        f"\n  Budget:          ${sim['total_budget']:.2f}",
        f"  Portfolio Value: ${port_value:.2f}",
        f"  Total P&L:       ${net_pnl:+.2f}  ({total_pct:+.2f}%)",
        "\nDISCLAIMER: Paper trading only. Not financial advice.",
    ]
    return "\n".join(lines)


def send_email(subject: str, body: str):
    email_from = os.environ.get("EMAIL_FROM")
    email_pass = os.environ.get("EMAIL_PASSWORD")
    email_to   = os.environ.get("EMAIL_TO")  # comma-separated for multiple recipients

    if not all([email_from, email_pass, email_to]):
        print("[!] Email env vars missing: EMAIL_FROM, EMAIL_PASSWORD, EMAIL_TO")
        return

    recipients = [e.strip() for e in email_to.split(",")]

    msg = MIMEMultipart()
    msg["From"]    = email_from
    msg["To"]      = ", ".join(recipients)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(email_from, email_pass)
            server.sendmail(email_from, recipients, msg.as_string())
        print(f"  Email sent to {', '.join(recipients)}")
    except Exception as e:
        print(f"  [!] Email failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="Paper trading tracker")
    parser.add_argument("--close",   metavar="SYMBOL", help="Close a position at current price")
    parser.add_argument("--history", action="store_true", help="Show snapshot history for all trades")
    parser.add_argument("--email",   action="store_true", help="Send status email after update")
    args = parser.parse_args()

    if args.history:
        show_history()
        return

    data, prices = update_and_display(close_symbol=args.close)

    if args.email:
        today = str(date.today())
        body = build_email_body(data, prices, today)
        send_email(f"Paper Portfolio Update - {today}", body)


if __name__ == "__main__":
    main()
