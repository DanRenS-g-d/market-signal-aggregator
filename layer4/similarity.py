"""
Layer 4.5: Similarity Engine
- Downloads max available historical data from Yahoo Finance
- Computes RSI, MACD, SMA for each day
- Labels successful trades using majority vote of 3 definitions
- Compares current conditions against corpus -> match score
"""

import os, sys
import math
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_connection
from config import PAIRS, TICKERS

YAHOO_MAP = {
    "EC": "EC",
    "CNEC.CN": "CNE.TO",
    "CIB": "CIB",
    "PFBCOLOM.CL": "PFBCOLOM.CL",
}

PAIR_MAP = {
    "EC": "CNEC.CN",
    "CNEC.CN": "EC",
    "CIB": "PFBCOLOM.CL",
    "PFBCOLOM.CL": "CIB",
}


# ── Technical indicators ──────────────────────────────────────

def compute_rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i-1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def compute_macd_signal(closes):
    if len(closes) < 35:
        return None
    def ema(data, n):
        k = 2 / (n + 1)
        result = [data[0]]
        for p in data[1:]:
            result.append(p * k + result[-1] * (1 - k))
        return result
    ema12 = ema(closes, 12)
    ema26 = ema(closes, 26)
    macd = [a - b for a, b in zip(ema12, ema26)]
    signal_line = ema(macd, 9)
    if macd[-1] > signal_line[-1]:
        return "bullish"
    return "bearish"


def compute_sma20_signal(closes):
    if len(closes) < 20:
        return None
    sma = sum(closes[-20:]) / 20
    return "bullish" if closes[-1] > sma else "bearish"


def compute_volume_zscore(volumes, window=20):
    if len(volumes) < window:
        return 0.0
    recent = volumes[-window:]
    mean = sum(recent) / window
    std = math.sqrt(sum((v - mean)**2 for v in recent) / window)
    if std == 0:
        return 0.0
    return round((volumes[-1] - mean) / std, 2)


# ── Bootstrap historical data ─────────────────────────────────

def bootstrap_ticker(ticker: str):
    try:
        import yfinance as yf
    except ImportError:
        print(f"    [Similarity] yfinance not installed, skipping bootstrap")
        return 0

    symbol = YAHOO_MAP.get(ticker, ticker)
    partner = PAIR_MAP.get(ticker)
    partner_symbol = YAHOO_MAP.get(partner, partner) if partner else None

    print(f"    [Similarity] Downloading {symbol} (max history)...")
    try:
        hist = yf.Ticker(symbol).history(period="max")
        if hist.empty:
            print(f"    [Similarity] No data for {symbol}")
            return 0

        partner_hist = None
        if partner_symbol:
            partner_hist = yf.Ticker(partner_symbol).history(period="max")

        closes = hist["Close"].tolist()
        volumes = hist["Volume"].tolist()
        dates = [d.date() for d in hist.index]

        conn = get_connection()
        cur = conn.cursor()
        inserted = 0

        for i in range(35, len(closes)):
            d = dates[i]
            window_closes = closes[max(0, i-50):i+1]
            window_volumes = volumes[max(0, i-20):i+1]

            rsi = compute_rsi(window_closes)
            macd_sig = compute_macd_signal(window_closes)
            sma_sig = compute_sma20_signal(window_closes)
            vol_z = compute_volume_zscore(window_volumes)

            # Label: definition 1 — price +2% in next 5 days
            def1 = False
            if i + 5 < len(closes) and closes[i] > 0:
                pct = (closes[i+5] - closes[i]) / closes[i] * 100
                def1 = pct > 2.0

            # Label: definition 2 — outperforms pair partner
            def2 = False
            if partner_hist is not None and not partner_hist.empty:
                partner_closes = partner_hist["Close"].tolist()
                partner_dates = [d2.date() for d2 in partner_hist.index]
                if d in partner_dates and i + 5 < len(closes):
                    pi = partner_dates.index(d)
                    if pi + 5 < len(partner_closes) and partner_closes[pi] > 0 and closes[i] > 0:
                        own_ret = (closes[i+5] - closes[i]) / closes[i]
                        par_ret = (partner_closes[pi+5] - partner_closes[pi]) / partner_closes[pi]
                        def2 = own_ret > par_ret

            # Label: definition 3 — RSI oversold + bounced
            def3 = False
            if rsi and rsi < 35 and i + 3 < len(closes):
                def3 = closes[i+3] > closes[i]

            votes = sum([def1, def2, def3])
            is_successful = votes >= 2
            price_change_5d = None
            if i + 5 < len(closes) and closes[i] > 0:
                price_change_5d = round((closes[i+5] - closes[i]) / closes[i] * 100, 4)

            try:
                cur.execute("""
                    INSERT INTO similarity_corpus
                        (ticker, date, rsi, macd_signal, sma20_signal,
                         volume_zscore, price_change_5d, pair_outperform,
                         rsi_bounce, is_successful, success_votes)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (ticker, date) DO NOTHING
                """, (ticker, d, rsi, macd_sig, sma_sig, vol_z,
                      price_change_5d, def2, def3, is_successful, votes))
                inserted += 1
            except Exception:
                pass

        conn.commit(); cur.close(); conn.close()
        print(f"    [Similarity] {ticker}: {inserted} days bootstrapped")
        return inserted

    except Exception as e:
        print(f"    [Similarity] Error bootstrapping {ticker}: {e}")
        return 0


def bootstrap_all():
    print(f"\n[Similarity] Bootstrapping historical corpus...")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM similarity_corpus")
    count = cur.fetchone()[0]
    cur.close(); conn.close()

    if count > 500:
        print(f"    [Similarity] Corpus already has {count} records, skipping bootstrap")
        return

    total = 0
    for ticker in TICKERS:
        total += bootstrap_ticker(ticker)
    print(f"    [Similarity] Bootstrap complete: {total} total records")


# ── Similarity matching ───────────────────────────────────────

def encode_conditions(rsi, macd_signal, sma20_signal, volume_zscore=0):
    """Encode current conditions as a numeric vector."""
    return [
        (rsi or 50) / 100.0,
        1.0 if macd_signal == "bullish" else (0.0 if macd_signal == "bearish" else 0.5),
        1.0 if sma20_signal == "bullish" else (0.0 if sma20_signal == "bearish" else 0.5),
        min(max((volume_zscore or 0) / 3.0, -1), 1),
    ]


def cosine_similarity(a, b):
    dot = sum(x*y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x**2 for x in a))
    mag_b = math.sqrt(sum(x**2 for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.5
    return dot / (mag_a * mag_b)


def get_similarity_score_for_ticker(ticker: str, rsi, macd_signal, sma20_signal) -> dict:
    """Compare current conditions against historical corpus. Returns match score."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT rsi, macd_signal, sma20_signal, volume_zscore, is_successful
        FROM similarity_corpus
        WHERE ticker = %s AND is_successful IS NOT NULL
        ORDER BY date DESC
        LIMIT 500
    """, (ticker,))
    rows = cur.fetchall()
    cur.close(); conn.close()

    if not rows:
        return {"score": 0.5, "matches": 0, "success_rate": 0.5}

    current = encode_conditions(rsi, macd_signal, sma20_signal)
    similarities = []

    for row in rows:
        h_rsi, h_macd, h_sma, h_vol, h_success = row
        historical = encode_conditions(h_rsi, h_macd, h_sma, h_vol or 0)
        sim = cosine_similarity(current, historical)
        similarities.append((sim, h_success))

    # Top 20 most similar setups
    top = sorted(similarities, key=lambda x: x[0], reverse=True)[:20]
    if not top:
        return {"score": 0.5, "matches": 0, "success_rate": 0.5}

    avg_sim = sum(s for s, _ in top) / len(top)
    success_rate = sum(1 for _, ok in top if ok) / len(top)

    # Combined score: similarity * success_rate
    score = round(avg_sim * success_rate, 3)

    return {
        "score": score,
        "matches": len(top),
        "success_rate": round(success_rate, 3),
        "avg_similarity": round(avg_sim, 3),
    }


def run_similarity_engine(tech_data: dict) -> dict:
    """
    tech_data: {ticker: {rsi, macd_signal, sma20_signal}}
    Returns similarity scores per ticker.
    """
    print(f"\n[Similarity] Matching current conditions vs corpus...")
    bootstrap_all()

    results = {}
    for ticker, tech in tech_data.items():
        result = get_similarity_score_for_ticker(
            ticker,
            tech.get("rsi"),
            tech.get("macd_signal"),
            tech.get("sma20_signal"),
        )
        results[ticker] = result
        print(f"    {ticker}: score={result['score']:.3f} "
              f"success_rate={result['success_rate']:.2f} "
              f"matches={result['matches']}")
    return results