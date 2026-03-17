---
name: Paper Trading Simulation
description: Current paper trading simulation state, trades, and decision history
type: project
---

Simulation period: 2026-03-14 to 2026-03-21
Budget: $1,000 (fully allocated, fractional shares, score-weighted)

**Current open trades (as of 2026-03-16):**

| Symbol | Dir | Entry | Shares | Alloc | Stop | TP1 | TP2 |
|--------|-----|-------|--------|-------|------|-----|-----|
| SQQQ | LONG | $73.21 | 5.123 | $375 | $71.26 | $77.11 | $81.01 |
| COIN | LONG | $195.53 | 1.662 | $325 | $188.88 | $208.83 | $222.13 |
| PLTR | LONG | $150.95 | 1.987 | $300 | $147.68 | $157.50 | $164.05 |

**Closed trades:**
- MARA: opened $9.32, closed $9.23 on 2026-03-16, P&L -$3.62 (-0.97%)
  - Reason: rotated into SQQQ as market hedge on bearish signals

**Decision history:**
- 2026-03-14: Opened MARA (A tier, score 75), COIN (B, 65), PLTR (B, 60)
- 2026-03-16: Analyzer showed SQQQ scoring 68 with bearish market signals (gap -3.2%, MACD bullish, EMA uptrend on inverse ETF). Closed MARA (-$3.62), opened SQQQ as hedge.

**Plan for end of week (2026-03-21):**
- Review results
- If strategy looks solid, connect to thinkorswim for real trading

**Why:** Paper trading to validate the analyzer signals before risking real money.
**How to apply:** When Howard checks in, pull paper_trades.json from GitHub or run `python paper_trades.py` in C:\Users\howar\Documents\stock_analyzer\ to get current P&L, then advise hold/close/adjust.
