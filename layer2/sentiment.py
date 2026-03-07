"""
LAYER 2: Sentiment Analysis via FinBERT
Fixes applied:
  1. Minimum article threshold (< 3 → neutral)
  2. Confidence weighting: score * log(1 + article_count)
  3. Dead zone: |adjusted_score| < 0.15 → neutral
  4. Fuzzy deduplication by headline similarity
  5. Macro oil price input for EC, GPRK, CNEC.CN
"""

import sys, os, math, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from datetime import datetime, timedelta
from db import get_connection, init_sentiment_table
from layer2.relevance import filter_articles

HF_API_URL = "https://router.huggingface.co/hf-inference/models/ProsusAI/finbert"
HF_TOKEN   = os.environ.get("HF_TOKEN", "")

# Tickers where oil price is a macro input
OIL_TICKERS = {"EC", "GPRK", "CNEC.CN"}

MIN_ARTICLES  = 3      # below this → neutral regardless of score
DEAD_ZONE     = 0.15   # |adjusted_score| below this → neutral
FUZZY_THRESH  = 0.6    # headline similarity above this → duplicate


# ── Fuzzy deduplication ───────────────────────────────────────────────────────

def _tokenize(text: str) -> set:
    return set(re.sub(r'[^a-z0-9 ]', '', text.lower()).split())

def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)

def deduplicate_articles(articles: list[dict]) -> list[dict]:
    """Remove near-duplicate headlines (same story from Reuters/Yahoo/Bloomberg/etc)."""
    kept = []
    for art in articles:
        title = art.get("title", "")
        is_dup = any(_jaccard(title, k.get("title", "")) >= FUZZY_THRESH for k in kept)
        if not is_dup:
            kept.append(art)
    removed = len(articles) - len(kept)
    if removed:
        print(f"    Dedup: removed {removed} near-duplicate headlines")
    return kept


# ── Oil price macro signal ────────────────────────────────────────────────────

def get_oil_macro_signal() -> dict:
    """
    Fetch Brent crude price change via Yahoo Finance yfinance.
    Returns: {"signal": "bullish"|"bearish"|"neutral", "change_pct": float}
    """
    try:
        import yfinance as yf
        hist = yf.Ticker("BZ=F").history(period="5d")
        if hist.empty or len(hist) < 2:
            return {"signal": "neutral", "change_pct": 0.0}
        closes = hist["Close"].tolist()
        change_pct = (closes[-1] - closes[-2]) / closes[-2] * 100
        if change_pct > 1.5:
            signal = "bullish"
        elif change_pct < -1.5:
            signal = "bearish"
        else:
            signal = "neutral"
        print(f"    [Oil Macro] Brent {change_pct:+.2f}% → {signal}")
        return {"signal": signal, "change_pct": round(change_pct, 3)}
    except Exception as e:
        print(f"    [Oil Macro] Error: {e}")
        return {"signal": "neutral", "change_pct": 0.0}


def apply_oil_macro(score: float, oil: dict) -> float:
    """
    Blend oil macro signal into sentiment score for oil tickers.
    Oil gets 30% weight, sentiment 70%.
    """
    oil_score = {"bullish": 0.3, "bearish": -0.3, "neutral": 0.0}[oil["signal"]]
    return round(score * 0.7 + oil_score * 0.3, 4)


# ── FinBERT scoring ───────────────────────────────────────────────────────────

def score_text(text: str) -> dict:
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    try:
        response = requests.post(
            HF_API_URL,
            headers=headers,
            json={"inputs": text[:512]},
            timeout=15,
        )
        if response.status_code == 200:
            results = response.json()
            if isinstance(results, list) and len(results) > 0:
                scores = results[0] if isinstance(results[0], list) else results
                score_map = {item["label"].lower(): item["score"] for item in scores}
                return {
                    "positive": score_map.get("positive", 0),
                    "negative": score_map.get("negative", 0),
                    "neutral":  score_map.get("neutral", 0),
                }
        elif response.status_code == 503:
            print(f"    [FinBERT] Model loading, retrying in 10s...")
            import time; time.sleep(10)
            return score_text(text)
        else:
            print(f"    [FinBERT] Error {response.status_code}: {response.text[:200]}")
    except Exception as e:
        print(f"    [FinBERT] Exception: {e}")
    return {"positive": 0, "negative": 0, "neutral": 1}


# ── DB helpers ────────────────────────────────────────────────────────────────

def get_recent_news(ticker: str, hours: int = 24) -> list[dict]:
    conn = get_connection()
    cur = conn.cursor()
    since = datetime.utcnow() - timedelta(hours=hours)
    cur.execute("""
        SELECT DISTINCT ON (title) id, title, summary, link
        FROM news
        WHERE ticker = %s AND fetched_at >= %s
        ORDER BY title, fetched_at DESC
    """, (ticker, since))
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [{"id": r[0], "title": r[1], "summary": r[2], "link": r[3]} for r in rows]


# ── Main analysis ─────────────────────────────────────────────────────────────

def analyze_ticker(ticker: str, oil_macro: dict | None = None) -> dict:
    news_items = get_recent_news(ticker, hours=24)
    if not news_items:
        news_items = get_recent_news(ticker, hours=168)

    if not news_items:
        print(f"    No news found for {ticker}")
        return {"ticker": ticker, "signal": "neutral", "score": 0.0,
                "adjusted_score": 0.0, "article_count": 0}

    # 1. Relevance filter
    relevant, stats = filter_articles(ticker, news_items)
    if stats["filtered"] > 0:
        print(f"    Relevance filter: {stats['relevant']}/{stats['total']} kept")

    if not relevant:
        print(f"    No relevant articles after filtering for {ticker}")
        return {"ticker": ticker, "signal": "neutral", "score": 0.0,
                "adjusted_score": 0.0, "article_count": 0}

    # 2. Fuzzy deduplication
    relevant = deduplicate_articles(relevant)

    # 3. Minimum article threshold
    if len(relevant) < MIN_ARTICLES:
        print(f"    Too few articles ({len(relevant)} < {MIN_ARTICLES}) → forced neutral")
        return {"ticker": ticker, "signal": "neutral", "score": 0.0,
                "adjusted_score": 0.0, "article_count": len(relevant),
                "reason": "min_articles"}

    print(f"    Scoring {len(relevant)} articles for {ticker}...")

    total_pos = total_neg = total_neu = 0
    scored = 0

    for item in relevant:
        text = (item["title"] or "")
        if item["summary"]:
            text += ". " + item["summary"][:200]
        s = score_text(text.strip())
        total_pos += s["positive"]
        total_neg += s["negative"]
        total_neu += s["neutral"]
        scored += 1
        print(f"      [{scored}] pos={s['positive']:.2f} neg={s['negative']:.2f} | {item['title'][:60]}")

    if scored == 0:
        return {"ticker": ticker, "signal": "neutral", "score": 0.0,
                "adjusted_score": 0.0, "article_count": 0}

    avg_pos  = total_pos / scored
    avg_neg  = total_neg / scored
    avg_neu  = total_neu / scored
    raw_score = round(avg_pos - avg_neg, 4)

    # 4. Confidence weighting: score * log(1 + n)
    weight = math.log(1 + scored)
    weighted_score = round(raw_score * weight, 4)

    # 5. Oil macro blend for oil tickers
    if ticker in OIL_TICKERS and oil_macro:
        weighted_score = apply_oil_macro(weighted_score, oil_macro)
        print(f"    [Oil blend] raw={raw_score:+.3f} → macro-adjusted={weighted_score:+.3f}")

    # 6. Dead zone
    if abs(weighted_score) < DEAD_ZONE:
        signal = "neutral"
        print(f"    Dead zone: |{weighted_score:.3f}| < {DEAD_ZONE} → neutral")
    elif weighted_score > 0:
        signal = "bullish"
    else:
        signal = "bearish"

    return {
        "ticker":        ticker,
        "signal":        signal,
        "score":         weighted_score,
        "raw_score":     raw_score,
        "avg_positive":  round(avg_pos, 4),
        "avg_negative":  round(avg_neg, 4),
        "avg_neutral":   round(avg_neu, 4),
        "article_count": scored,
    }


def run_sentiment_analysis():
    from config import TICKERS
    print(f"\n{'='*50}")
    print(f"Layer 2: Sentiment Analysis at {datetime.utcnow().isoformat()}")
    print(f"{'='*50}")

    if not HF_TOKEN:
        print("[ERROR] HF_TOKEN not set.")
        return

    init_sentiment_table()

    # Fetch oil macro once, reuse for all oil tickers
    print("\n[Macro] Fetching Brent crude...")
    oil_macro = get_oil_macro_signal()

    conn = get_connection()
    cur = conn.cursor()
    results = []

    for ticker in TICKERS:
        print(f"\n[→] Analyzing {ticker}")
        macro = oil_macro if ticker in OIL_TICKERS else None
        result = analyze_ticker(ticker, oil_macro=macro)
        results.append(result)

        cur.execute("""
            INSERT INTO sentiment
                (ticker, signal, score, avg_positive, avg_negative, avg_neutral, article_count)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            result["ticker"], result["signal"], result["score"],
            result.get("avg_positive", 0), result.get("avg_negative", 0),
            result.get("avg_neutral", 0), result.get("article_count", 0),
        ))
        print(f"    → SIGNAL: {result['signal'].upper()} (score={result['score']})")

    conn.commit(); cur.close(); conn.close()
    print(f"\n[✓] Sentiment analysis complete. Results saved.")
    return results


if __name__ == "__main__":
    run_sentiment_analysis()