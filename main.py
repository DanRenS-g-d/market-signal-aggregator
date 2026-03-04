"""
Main entry point for market-signal-aggregator.
Runs Layer 1 (ingestion) then Layer 2 (sentiment) on a schedule.
"""

import schedule
import time
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from db import init_db, init_sentiment_table
from config import TICKERS
from layer1.scrapers import fetch_google_news, compute_technicals, fetch_twitter
from db import insert_news, insert_technicals, insert_tweets
from layer2.sentiment import run_sentiment_analysis

INTERVAL = int(os.environ.get("FETCH_INTERVAL_HOURS", 6))


def run_pipeline():
    print(f"\n{'='*60}")
    print(f"PIPELINE RUN at {datetime.utcnow().isoformat()}")
    print(f"{'='*60}")

    # ── LAYER 1 ──────────────────────────────────────────────
    print("\n[LAYER 1] Data Ingestion")
    for ticker in TICKERS:
        print(f"\n  [→] {ticker}")

        news = fetch_google_news(ticker)
        insert_news(news)
        print(f"      News: {len(news)} items")

        tech = compute_technicals(ticker)
        insert_technicals(tech)
        print(f"      Technicals: RSI={tech.get('rsi','N/A')} | MACD={tech.get('macd_signal','N/A')}")

        tweets = fetch_twitter(ticker)
        insert_tweets(tweets)
        print(f"      Tweets: {len(tweets)}")

    # ── LAYER 2 ──────────────────────────────────────────────
    print("\n[LAYER 2] Sentiment Analysis")
    results = run_sentiment_analysis()

    if results:
        print("\n── SUMMARY ──────────────────────────────────────────")
        for r in results:
            bar = "▲" if r["signal"] == "bullish" else ("▼" if r["signal"] == "bearish" else "─")
            print(f"  {bar} {r['ticker']:12} {r['signal'].upper():8} score={r['score']:+.3f}  ({r.get('article_count',0)} articles)")
        print("─────────────────────────────────────────────────────")

    print(f"\n[✓] Pipeline complete. Next run in {INTERVAL} hours.")


if __name__ == "__main__":
    print("market-signal-aggregator starting...")
    print(f"Tickers: {TICKERS}")
    print(f"Interval: every {INTERVAL} hours")

    # Init DB tables
    init_db()
    init_sentiment_table()

    # Run immediately
    run_pipeline()

    # Schedule
    schedule.every(INTERVAL).hours.do(run_pipeline)

    while True:
        schedule.run_pending()
        time.sleep(60)