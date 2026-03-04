"""
LAYER 2: Sentiment Analysis via FinBERT
Reads news from DB, scores each title, saves aggregate sentiment per ticker.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import json
from datetime import datetime, timedelta
from db import get_connection, init_sentiment_table

HF_API_URL = "https://router.huggingface.co/hf-inference/models/ProsusAI/finbert"
HF_TOKEN = os.environ.get("HF_TOKEN", "")


def score_text(text: str) -> dict:
    """Send text to FinBERT via HuggingFace Inference API. Returns {positive, negative, neutral}."""
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    try:
        response = requests.post(
            HF_API_URL,
            headers=headers,
            json={"inputs": text[:512]},  # FinBERT max 512 tokens
            timeout=15,
        )
        if response.status_code == 200:
            results = response.json()
            # HF returns list of list of dicts: [[{label, score}, ...]]
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


def get_recent_news(ticker: str, hours: int = 24) -> list[dict]:
    """Fetch news from DB from the last N hours for a ticker."""
    conn = get_connection()
    cur = conn.cursor()
    since = datetime.utcnow() - timedelta(hours=hours)
    cur.execute("""
        SELECT DISTINCT ON (title) id, title, summary
        FROM news
        WHERE ticker = %s AND fetched_at >= %s
        ORDER BY title, fetched_at DESC
    """, (ticker, since))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"id": r[0], "title": r[1], "summary": r[2]} for r in rows]


def analyze_ticker(ticker: str) -> dict:
    """Score all recent news for a ticker and return aggregate sentiment."""
    news_items = get_recent_news(ticker, hours=24)

    if not news_items:
        # Fall back to last 7 days if nothing in 24h
        news_items = get_recent_news(ticker, hours=168)

    if not news_items:
        print(f"    No news found for {ticker}")
        return {"ticker": ticker, "signal": "neutral", "score": 0.0, "article_count": 0}

    print(f"    Scoring {len(news_items)} articles for {ticker}...")

    total_positive = 0
    total_negative = 0
    total_neutral = 0
    scored = 0

    for item in news_items:
        text = item["title"] or ""
        if item["summary"]:
            text += ". " + item["summary"][:200]

        scores = score_text(text.strip())
        total_positive += scores["positive"]
        total_negative += scores["negative"]
        total_neutral  += scores["neutral"]
        scored += 1

        print(f"      [{scored}] pos={scores['positive']:.2f} neg={scores['negative']:.2f} | {item['title'][:60]}")

    if scored == 0:
        return {"ticker": ticker, "signal": "neutral", "score": 0.0, "article_count": 0}

    avg_pos = total_positive / scored
    avg_neg = total_negative / scored
    avg_neu = total_neutral  / scored

    # Net sentiment score: positive - negative, range -1 to 1
    net_score = round(avg_pos - avg_neg, 4)

    if net_score > 0.1:
        signal = "bullish"
    elif net_score < -0.1:
        signal = "bearish"
    else:
        signal = "neutral"

    return {
        "ticker":        ticker,
        "signal":        signal,
        "score":         net_score,
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
        print("[ERROR] HF_TOKEN not set. Get a free token at huggingface.co/settings/tokens")
        return

    init_sentiment_table()

    conn = get_connection()
    cur = conn.cursor()

    results = []
    for ticker in TICKERS:
        print(f"\n[→] Analyzing {ticker}")
        result = analyze_ticker(ticker)
        results.append(result)

        cur.execute("""
            INSERT INTO sentiment
                (ticker, signal, score, avg_positive, avg_negative, avg_neutral, article_count)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            result["ticker"],
            result["signal"],
            result["score"],
            result.get("avg_positive", 0),
            result.get("avg_negative", 0),
            result.get("avg_neutral", 0),
            result.get("article_count", 0),
        ))

        print(f"    → SIGNAL: {result['signal'].upper()} (score={result['score']})")

    conn.commit()
    cur.close()
    conn.close()

    print(f"\n[✓] Sentiment analysis complete. Results saved.")
    return results


if __name__ == "__main__":
    run_sentiment_analysis()