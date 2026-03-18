---
name: Paper Trading Simulation
description: Current paper trading simulation state, trades, and decision history
type: project
---

Simulation period: 2026-03-14 to 2026-03-21
Budget: $1,000 (fully allocated, fractional shares, score-weighted)

**Current open trades (as of 2026-03-18):**

| Symbol | Dir | Entry | Shares | Alloc | Stop | TP1 | TP2 |
|--------|-----|-------|--------|-------|------|-----|-----|
| PLTR | LONG | $150.95 | 1.987 | $300 | $147.68 | $157.50 | $164.05 |
| NVDA | LONG | $116.78 | 3.425 | $400 | $114.78 | $120.78 | $124.78 |
| TQQQ | LONG | $67.24 | 4.387 | $295 | $65.74 | $70.24 | $73.24 |

Cash remaining: $25.10 | Realized P&L: $16.48

**Closed trades:**
- MARA: opened $9.32, closed $9.23 on 2026-03-16, P&L -$3.62 (-0.97%)
  - Reason: rotated into SQQQ as market hedge on bearish signals
- COIN: opened $195.53, closed $210.89 (TP1 hit), P&L +$25.53 (+7.86%)
- SQQQ: opened $73.21, closed $72.15 on 2026-03-18, P&L -$5.43 (-1.45%)
  - Reason: bearish thesis not playing out, 3 days left in period, freed cash to go long

**Decision history:**
- 2026-03-14: Opened MARA (A tier, score 75), COIN (B, 65), PLTR (B, 60)
- 2026-03-16: Analyzer showed SQQQ scoring 68 with bearish market signals. Closed MARA (-$3.62), opened SQQQ as hedge.
- 2026-03-18: Closed SQQQ (-$5.43) — bearish thesis weak with 3 days left. Deployed freed cash + existing cash into NVDA ($400) and TQQQ ($295). All-in bull stance on tech/Nasdaq for final stretch of simulation period.

**Plan for end of week (2026-03-21):**
- Review results
- If strategy looks solid, connect to thinkorswim for real trading

**Why:** Paper trading to validate the analyzer signals before risking real money.
**How to apply:** When Howard checks in, pull paper_trades.json from GitHub or run `python paper_trades.py` in C:\Users\howar\Documents\stock_analyzer\ to get current P&L, then advise hold/close/adjust.
