# Market Signal Aggregator
 
A quantitative trading signal system for Latin American and global emerging market equities. Built from scratch over 3 months while working full time.
 
## What It Does
 
The system runs every 6 hours on Railway cloud infrastructure. It ingests data from multiple sources, processes it through 8 analytical layers, applies risk management rules, and delivers actionable trading signals via Telegram.
 
After ablation testing on 400+ paper trades, the system was pruned to 13 high-alpha pairs focused on Latin American relative value — where market inefficiencies are strongest.
 
**Live accuracy: 66.8% on 400 resolved paper trades (threshold: 55%)**
 
---
 
## Architecture
 
```
Data Sources → Layer 1 (Ingestion) → Layer 2 (FinBERT Sentiment)
→ Layer 4.5 (Similarity Engine) → Regime Detector
→ Layer 4 (Signal Generation) → Enrichment Layers
→ Risk Management → Outputs (Telegram, Twitter, DB)
```
 
### Data Sources
 
| Source | Purpose |
|--------|---------|
| Google News RSS | News articles per ticker |
| Alpha Vantage | Technical indicators (NYSE tickers) |
| yfinance | Prices, technicals (BVC tickers, ETFs, bonds, forex) |
| FRED API | 12 macro series (retail sales, PCE, CPI, Fed funds) |
| aisstream.io | AIS vessel tracking — oil tanker congestion signals |
| Polymarket | Prediction market probabilities for divergence detection |
| VIX (^VIX) | Market fear index, put/call ratios |
 
### Layers
 
**Layer 1 — Data Ingestion**
Fetches news, technicals, forex prices, macro data, marine AIS, VIX, and Polymarket probabilities for all 24 tickers.
 
**Layer 2 — Sentiment Analysis**
Runs FinBERT on news articles with relevance filtering, dead zone (|score| < 0.15 → neutral), confidence weighting (score × log(1+n)), fuzzy deduplication (Jaccard ≥ 0.6), and oil macro blend for energy tickers.
 
**Layer 4.5 — Similarity Engine**
Bootstraps 54,000+ historical trading days from Yahoo Finance. Computes RSI, MACD, SMA20, spread, and volume for each day. Matches current conditions against corpus using cosine similarity.
 
**Regime Detector**
Evaluates each pair before signal generation using rolling Pearson correlation (60-day window), ATR volatility percentile (only trades in 30th–70th percentile), and correlation stability (std dev of rolling 20-day correlations). Computes `regime_score = corr_score × vol_score`. Pairs below threshold are skipped.
 
**Layer 4 — Signal Generation**
Combines sentiment scores, technical signals, and similarity scores into a pair vote system. Generates long_a, long_b, or neutral with a confidence score. Opens paper trades automatically.
 
**Enrichment Layers**
- Forex signals: translates stock signals into 12 correlated forex pairs with TP/SL
- Volatility: VIX level, put/call ratios, confidence multiplier adjustments
- Marine traffic: 7 maritime zones monitored for tanker congestion (EC/GPRK/EWZ signals)
- Macro consumer: 12 FRED series with seasonal percentile ranking and historical pattern matching
 
**Risk Management**
Position sizing by confidence (15% at conf=0.50, 30% at conf=0.75), stop loss -5%, take profit +10%, pair monitor (auto-disables pairs below 45% rolling accuracy), regime filter.
 
**Prediction Market Divergence**
Searches Polymarket with 100+ keywords in English and Spanish. Alerts when system confidence diverges from market-implied probability by more than 20 points — Soros-style mispricing detection.
 
---
 
## Universe
 
### Tickers (24 total)
 
**Colombia (NYSE-listed):** EC, GPRK, CIB, AVAL, TGLS
 
**Colombia (BVC):** CIBEST.CL, PFCIBEST.CL, ISA.CL, GEB.CL, GRUPSURA.CL, PFGRUPSURA.CL, CEMARGOS.CL, PFBCOLOM.CL, CNEC.CN
 
**Latin America ETFs:** EWZ, EWW, ECH, EPU
 
**Africa ETFs:** EZA, NGE
 
**Southeast Asia ETFs:** EWY, EWT, EIDO, THD
 
**Bond ETFs:** TLT, IEF, HYG, EMB
 
### Active Pairs (13 — post ablation)
 
| Pair | Tier | Accuracy | Avg P&L |
|------|------|----------|---------|
| Oil Integrated vs Gas | A | 100% | +5.62% |
| Brazil vs Mexico | A | 95% | +4.46% |
| CIB Ord vs Pfd | A | 100% | +4.28% |
| ISA vs GEB | A | 100% | +3.94% |
| Mexico vs Peru | A | 82% | +3.52% |
| Peru vs Chile | A | 100% | +3.30% |
| Brazil vs Chile | A | 100% | +2.96% |
| Sura vs Aval | A | 76% | +2.92% |
| Brazil vs Long Bonds | B | 65% | +2.28% |
| Oil Integrated vs E&P | B | 62% | +1.81% |
| Bancolombia vs Davivienda | B | 69% | +1.64% |
| E&P Oil vs Gas | B | 61% | +0.83% |
| South Africa vs Nigeria | B | 86% | +2.68% |
 
9 pairs removed after ablation (Cemargos, HY/IG bonds, Korea/Asia pairs, EM bonds).
 
---
 
## Backtesting & Validation
 
**Ablation testing** was performed on 400 resolved paper trades to identify which pairs add real alpha vs noise. Key findings:
 
- Confidence score miscalibrated: high confidence (≥0.75) underperforms mid confidence (0.50–0.74)
- Similarity score does not filter effectively at current thresholds
- Core alpha is in Colombia and Latam pairs — not Asian ETFs or bond spreads
- Walk-forward validation (70/30 split): 1.5% degradation — low overfitting risk
 
**Forward testing** began April 6, 2026 (post-ablation). All paper trades after this date are tagged `is_forward_test = TRUE` and tracked separately.
 
Run backtest report:
```bash
DATABASE_URL="..." python backtest.py
```
 
Run forward test report:
```bash
DATABASE_URL="..." python forward_test.py
```
 
---
 
## Infrastructure
 
| Component | Technology |
|-----------|-----------|
| Cloud runtime | Railway (runs every 6 hours) |
| Database | Railway PostgreSQL |
| NLP model | FinBERT (HuggingFace) |
| Notifications | Telegram Bot API |
| Public signals | Twitter API v2 (OAuth 1.0a) |
| Email | SendGrid |
 
---
 
## Project Structure
 
```
market-signal-aggregator/
├── main.py                  # Pipeline orchestrator
├── config.py                # Tickers, pairs, search terms
├── db.py                    # DB connection with retry logic
├── notifications.py         # SendGrid email
├── telegram_notify.py       # Telegram bot
├── twitter_publisher.py     # Twitter/X public signals
├── pair_monitor.py          # Auto-disable underperforming pairs
├── regime_detector.py       # Correlation + volatility regime filter
├── volatility.py            # VIX + put/call ratio module
├── forex_signals.py         # Stock-to-forex signal translation
├── forex_paper.py           # Forex paper trading tracker
├── forex_technicals.py      # RSI/MACD/SMA for forex pairs
├── prediction_markets.py    # Polymarket divergence detection
├── marine_traffic.py        # AIS oil tanker signal (aisstream.io)
├── macro_consumer.py        # FRED macro consumer cycle signals
├── backtest.py              # Formal backtesting (Sharpe, Calmar, drawdown)
├── forward_test.py          # Out-of-sample forward test framework
├── layer1/                  # Data ingestion (news, technicals, Twitter)
├── layer2/                  # FinBERT sentiment + relevance filter
└── layer4/                  # Signal generation, similarity engine, accuracy
```
 
---
 
## Key Commands
 
```bash
# Accuracy report
python layer4/accuracy.py
 
# Formal backtest (Sharpe, drawdown, walk-forward)
python backtest.py
 
# Forward test (out-of-sample)
python forward_test.py
 
# Regime status for all pairs
python regime_detector.py
 
# Forex paper trading accuracy
python forex_paper.py
 
# Test marine traffic (AIS)
python marine_traffic.py
```
 
---
 
## Environment Variables
 
```env
DATABASE_URL=postgresql://...
SENDGRID_API_KEY=...
HF_TOKEN=...                    # HuggingFace for FinBERT
ALPHA_VANTAGE_KEY=...
TELEGRAM_TOKEN=...
TELEGRAM_CHAT_ID=...
TWITTER_API_KEY=...
TWITTER_API_SECRET=...
TWITTER_ACCESS_TOKEN=...
TWITTER_ACCESS_TOKEN_SECRET=...
AISSTREAM_API_KEY=...
FRED_API_KEY=...
SUBSCRIBE_LINK=...
FETCH_INTERVAL_HOURS=6
```
 
---
 
## Methodology Notes
 
This system exploits relative value inefficiencies in Latin American markets. The signal edge comes from:
 
1. **Information asymmetry** — FinBERT processes Spanish and English news faster than manual analysis
2. **Regime-filtered pairs trading** — only trade when correlation and volatility conditions are right
3. **Historical pattern matching** — 30+ years of macro data to contextualize current conditions
4. **Alternative data** — marine tanker movements and prediction market divergences as confirmation signals
 
The system is not a black box. Every signal has an interpretable source, and every component was validated empirically before inclusion.
 
---
 
## Disclaimer
 
This system is for research and educational purposes. Past paper trading performance does not guarantee future results. This is not financial advice.
