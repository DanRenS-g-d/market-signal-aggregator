import schedule
import time
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from db import init_db, init_sentiment_table, insert_news, insert_technicals, insert_tweets, technicals_fetched_today
from config import TICKERS
from layer1.scrapers import fetch_google_news, compute_technicals, fetch_twitter
from layer2.sentiment import run_sentiment_analysis
from layer3.prediction_market import run_prediction_market_layer

INTERVAL = int(os.environ.get("FETCH_INTERVAL_HOURS", 6))


def run_pipeline():
    print(f"\n{'='*60}")
    print(f"PIPELINE RUN at {datetime.utcnow().isoformat()}")
    print(f"{'='*60}")

    # LAYER 1
    print("\n[LAYER 1] Data Ingestion")
    for ticker in TICKERS:
        print(f"\n  [->] {ticker}")
        news = fetch_google_news(ticker)
        inserted = insert_news(news)
        print(f"      News: {inserted} new items (fetched {len(news)})")

        if technicals_fetched_today(ticker):
            print(f"      Technicals: skipped (already fetched today)")
        else:
            tech = compute_technicals(ticker)
            insert_technicals(tech)
            print(f"      Technicals: RSI={tech.get('rsi','N/A')} | MACD={tech.get('macd_signal','N/A')}")

        tweets = fetch_twitter(ticker)
        insert_tweets(tweets)
        print(f"      Tweets: {len(tweets)}")

    # LAYER 2
    print("\n[LAYER 2] Sentiment Analysis")
    sentiment_results = run_sentiment_analysis()

    if sentiment_results:
        print("\n-- SENTIMENT SUMMARY --")
        for r in sentiment_results:
            bar = "^" if r["signal"] == "bullish" else ("v" if r["signal"] == "bearish" else "-")
            print(f"  {bar} {r['ticker']:12} {r['signal'].upper():8} score={r['score']:+.3f}")

    # LAYER 3
    print("\n[LAYER 3] Prediction Market Voting")
    pm_results = run_prediction_market_layer()

    if pm_results:
        print("\n-- PREDICTION MARKET SUMMARY --")
        for r in pm_results:
            print(f"  {r['pair']}: p_yes={r['probability_yes']:.3f} -> {r['signal'].upper()}")

    print(f"\n[OK] Pipeline complete. Next run in {INTERVAL} hours.")


if __name__ == "__main__":
    print("market-signal-aggregator starting...")
    print(f"Tickers: {TICKERS}")
    print(f"Interval: every {INTERVAL} hours")

    init_db()
    init_sentiment_table()

    run_pipeline()

    schedule.every(INTERVAL).hours.do(run_pipeline)

    while True:
        schedule.run_pending()
        time.sleep(60)