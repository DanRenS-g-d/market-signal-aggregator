# market-signal-aggregator

Pairs trading signal engine for Colombian markets.

## Architecture
- **Layer 1** — Data ingestion (Google News RSS, Yahoo Finance, Twitter/X)
- **Layer 2** — Sentiment analysis via FinBERT
- **Layer 3** — Prediction market integration (synthetic users)
- **Layer 4** — Signal generation (bull/bear per pair)
- **Layer 5** — Validation dashboard
- **Layer 6** — Execution via brokerage API

## Stack
- Python backend (Railway)
- PostgreSQL (Railway)
- React dashboard (Vercel)

## Pairs
- Ecopetrol (EC) vs Canacol (CNEC.CN)
- Bancolombia (CIB) vs Davivienda (PFBCOLOM.CL)

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# fill in your credentials in .env
python -m layer1.run
```
