"""
Layer 4.5: Similarity Engine — extended for all tickers.
"""

import os, sys, math
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_connection
from config import PAIRS, TICKERS, YAHOO_MAP

# Build pair partner map from config
PAIR_MAP = {}
for p in PAIRS:
    PAIR_MAP.setdefault(p["a"], p["b"])
    PAIR_MAP.setdefault(p["b"], p["a"])


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
    return round(100 - (100 / (1 + avg_gain / avg_loss)), 2)


def compute_macd_signal(closes):
    if len(closes) < 35:
        return None
    def ema(data, n):
        k = 2 / (n + 1)
        r = [data[0]]
        for p in data[1:]:
            r.append(p * k + r[-1] * (1 - k))
        return r
    macd = [a - b for a, b in zip(ema(closes, 12), ema(closes, 26))]
    sig = ema(macd, 9)
    return "bullish" if macd[-1] > sig[-1] else "bearish"


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
    return round((volumes[-1] - mean) / std, 2) if std else 0.0


def bootstrap_ticker(ticker: str):
    try:
        import yfinance as yf
    except ImportError:
        return 0

    symbol = YAHOO_MAP.get(ticker, ticker)
    partner = PAIR_MAP.get(ticker)
    partner_symbol = YAHOO_MAP.get(partner, partner) if partner else None

    print(f"    [Similarity] Downloading {symbol}...")
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
            wc = closes[max(0, i-50):i+1]
            wv = volumes[max(0, i-20):i+1]

            rsi = compute_rsi(wc)
            macd_sig = compute_macd_signal(wc)
            sma_sig = compute_sma20_signal(wc)
            vol_z = compute_volume_zscore(wv)

            def1 = False
            if i + 5 < len(closes) and closes[i] > 0:
                def1 = (closes[i+5] - closes[i]) / closes[i] * 100 > 2.0

            def2 = False
            if partner_hist is not None and not partner_hist.empty:
                pc = partner_hist["Close"].tolist()
                pd = [d2.date() for d2 in partner_hist.index]
                if d in pd and i + 5 < len(closes):
                    pi = pd.index(d)
                    if pi + 5 < len(pc) and pc[pi] > 0 and closes[i] > 0:
                        def2 = (closes[i+5] - closes[i]) / closes[i] > (pc[pi+5] - pc[pi]) / pc[pi]

            def3 = rsi and rsi < 35 and i + 3 < len(closes) and closes[i+3] > closes[i]

            votes = sum([def1, def2, def3])
            pct5 = round((closes[i+5] - closes[i]) / closes[i] * 100, 4) if i + 5 < len(closes) and closes[i] > 0 else None

            try:
                cur.execute("""
                    INSERT INTO similarity_corpus
                        (ticker, date, rsi, macd_signal, sma20_signal,
                         volume_zscore, price_change_5d, pair_outperform,
                         rsi_bounce, is_successful, success_votes)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (ticker, date) DO NOTHING
                """, (ticker, d, rsi, macd_sig, sma_sig, vol_z,
                      pct5, def2, bool(def3), votes >= 2, votes))
                inserted += 1
            except Exception:
                pass

        conn.commit(); cur.close(); conn.close()
        print(f"    [Similarity] {ticker}: {inserted} days")
        return inserted
    except Exception as e:
        print(f"    [Similarity] Error {ticker}: {e}")
        return 0


def bootstrap_all():
    print(f"\n[Similarity] Bootstrapping corpus for all tickers...")
    conn = get_connection()
    cur = conn.cursor()

    total = 0
    for ticker in TICKERS:
        cur.execute("SELECT COUNT(*) FROM similarity_corpus WHERE ticker=%s", (ticker,))
        count = cur.fetchone()[0]
        if count > 100:
            print(f"    [Similarity] {ticker}: already has {count} records, skipping")
        else:
            total += bootstrap_ticker(ticker)

    cur.close(); conn.close()
    print(f"    [Similarity] Bootstrap complete: {total} new records")


def encode_conditions(rsi, macd_signal, sma20_signal, volume_zscore=0):
    return [
        float(rsi or 50) / 100.0,
        1.0 if macd_signal == "bullish" else (0.0 if macd_signal == "bearish" else 0.5),
        1.0 if sma20_signal == "bullish" else (0.0 if sma20_signal == "bearish" else 0.5),
        min(max(float(volume_zscore or 0) / 3.0, -1), 1),
    ]


def cosine_similarity(a, b):
    dot = sum(x*y for x, y in zip(a, b))
    ma = math.sqrt(sum(x**2 for x in a))
    mb = math.sqrt(sum(x**2 for x in b))
    return dot / (ma * mb) if ma and mb else 0.5


def get_similarity_score_for_ticker(ticker, rsi, macd_signal, sma20_signal) -> dict:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT rsi, macd_signal, sma20_signal, volume_zscore, is_successful
        FROM similarity_corpus WHERE ticker=%s AND is_successful IS NOT NULL
        ORDER BY date DESC LIMIT 500
    """, (ticker,))
    rows = cur.fetchall()
    cur.close(); conn.close()

    if not rows:
        return {"score": 0.5, "matches": 0, "success_rate": 0.5}

    current = encode_conditions(rsi, macd_signal, sma20_signal)
    sims = [(cosine_similarity(current, encode_conditions(r[0], r[1], r[2], r[3] or 0)), r[4]) for r in rows]
    top = sorted(sims, key=lambda x: x[0], reverse=True)[:20]

    avg_sim = sum(s for s, _ in top) / len(top)
    success_rate = sum(1 for _, ok in top if ok) / len(top)
    return {
        "score": round(avg_sim * success_rate, 3),
        "matches": len(top),
        "success_rate": round(success_rate, 3),
    }


def run_similarity_engine(tech_data: dict) -> dict:
    print(f"\n[Similarity] Matching current conditions vs corpus...")
    bootstrap_all()

    results = {}
    for ticker, tech in tech_data.items():
        result = get_similarity_score_for_ticker(
            ticker, tech.get("rsi"), tech.get("macd_signal"), tech.get("sma20_signal")
        )
        results[ticker] = result
        print(f"    {ticker}: score={result['score']:.3f} success_rate={result['success_rate']:.2f} matches={result['matches']}")
    return results