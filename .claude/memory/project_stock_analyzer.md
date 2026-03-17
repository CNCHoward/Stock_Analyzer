---
name: Stock Analyzer App
description: Details about the stock analyzer app we built together
type: project
---

Stock analyzer app lives at: C:\Users\howar\Documents\stock_analyzer\
GitHub repo: https://github.com/CNCHoward/Stock_Analyzer (default branch: main)

Key files:
- stock_analyzer.py — main analyzer, scores stocks 0-100 using RSI, MACD, ATR, Volume, EMA, Gap
- paper_trades.py — paper trading tracker, run with `python paper_trades.py`
- paper_trades.json — current simulation state and trade snapshots
- requirements.txt — yfinance, pandas, numpy, rich, streamlit, plotly

Default watchlist: AAPL, MSFT, NVDA, TSLA, META, GOOGL, AMZN, AMD, PLTR, SOFI, MARA, RIOT, COIN, SPY, QQQ, SQQQ, TQQQ

Scoring tiers:
- 75-100: A STRONG
- 55-74: B GOOD
- 35-54: C WEAK
- 0-34: D SKIP

GitHub Actions workflow (paper_trades.yml) runs automatically:
- Mon-Fri 8:30 AM ET and 3:00 PM ET
- Fetches live prices, calculates P&L, emails status, commits snapshots back to repo
- Email recipients: howardcaton@gmail.com, Marvin.Bluedorn@gmail.com
- GitHub secrets set: EMAIL_FROM, EMAIL_PASSWORD, EMAIL_TO
- Can be triggered manually from GitHub Actions tab or via API

**Why:** To simulate and eventually automate real trades using technical analysis signals.
**How to apply:** When Howard says "check the trades" or "run the analyzer", use these files directly.
