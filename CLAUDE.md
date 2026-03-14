# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

**Streamlit web app (primary UI):**
```
"C:\Users\howar\AppData\Local\Python\pythoncore-3.14-64\python.exe" -m streamlit run app.py
```
Access at `http://localhost:8501`. The app auto-reloads on file save.

**CLI script (terminal only):**
```
"C:\Users\howar\AppData\Local\Python\pythoncore-3.14-64\python.exe" stock_analyzer.py
"C:\Users\howar\AppData\Local\Python\pythoncore-3.14-64\python.exe" stock_analyzer.py AAPL TSLA NVDA
"C:\Users\howar\AppData\Local\Python\pythoncore-3.14-64\python.exe" stock_analyzer.py --watch 5 --alert 70
```

**Install dependencies:**
```
"C:\Users\howar\AppData\Local\Python\pythoncore-3.14-64\python.exe" -m pip install -r requirements.txt
```

**Push changes to GitHub (auto-deploys to Streamlit Cloud):**
```
git add <files> && git commit -m "message" && git push origin master:main
```

## Architecture

The project is two files with a clean separation:

**`stock_analyzer.py`** — pure data/logic layer. No Streamlit imports. Contains:
- `analyze_ticker(symbol, fetch_premarket)` — main entry point. Fetches yfinance data, computes all indicators, returns a flat metrics `dict`
- `calc_trade_levels(price, atr, trend)` — computes entry/stop loss/take profit using 0.5× ATR risk and 1:2 reward ratio
- `score_stock(metrics)` — returns `(int score 0–100, list[str] reasons)` based on weighted indicator signals
- `load_watchlist()` / `save_watchlist()` — reads/writes `watchlist.json` next to the script
- `DEFAULT_WATCHLIST` — fallback list of 17 tickers used when no `watchlist.json` exists

**`app.py`** — Streamlit UI layer. Imports `stock_analyzer as sa` and calls its functions directly. Manages state via `st.session_state` (keys: `watchlist`, `results`, `last_run`). Contains no business logic.

## Key Design Decisions

- `stock_analyzer.py` is safe to `import` because `main()` is guarded by `if __name__ == "__main__"`. Never remove this guard.
- Company names use a hardcoded `_KNOWN_NAMES` dict as the **primary** source (inside `analyze_ticker`), with `ticker.info` as fallback. This is intentional — `ticker.info` is unreliable on cloud-hosted environments due to Yahoo Finance rate limiting.
- The local branch is `master` but the GitHub remote branch is `main`. Always push with `git push origin master:main`.
- Streamlit Cloud deployment is at `https://share.streamlit.io` connected to `github.com/CNCHoward/Stock_Analyzer`. Every push to `main` triggers an automatic redeploy.
- `watchlist.json` is not committed to the repo. On Streamlit Cloud, watchlist changes made through the UI do not persist across redeploys — the app falls back to `DEFAULT_WATCHLIST`.
