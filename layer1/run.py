import schedule
import time
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import init_db, insert_news, insert_technicals, insert_tweets
from config import TICKERS
from layer1.scrapers import fetch_google_news, compute_technicals, fetch_twitter

INTERVAL = int(os.environ.get("FETCH_INTERVAL_HOURS", 6))


def run_ingestion():
    print(f"\n{'='*50}")
    print(f"Ingestion run at {datetime.utcnow().isoformat()}")
    print(f"{'='*50}")

    for ticker in TICKERS:
        print(f"\n[→] {ticker}")

        news = fetch_google_news(ticker)
        insert_news(news)
        print(f"    News: {len(news)} items saved")

        tech = compute_technicals(ticker)
        insert_technicals(tech)
        print(f"    Technicals: RSI={tech.get('rsi','N/A')} | MACD={tech.get('macd_signal','N/A')} | SMA={tech.get('sma20_signal','N/A')}")

        tweets = fetch_twitter(ticker)
        insert_tweets(tweets)
        print(f"    Tweets: {len(tweets)} saved")

    print(f"\n[✓] Run complete.")


if __name__ == "__main__":
    print("market-signal-aggregator | Layer 1")
    print(f"Tickers: {TICKERS}")
    print(f"Interval: every {INTERVAL} hours\n")

    init_db()
    run_ingestion()

    schedule.every(INTERVAL).hours.do(run_ingestion)

    while True:
        schedule.run_pending()
        time.sleep(60)
