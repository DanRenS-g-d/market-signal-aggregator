import schedule
import time
import os
from datetime import datetime
from dotenv import load_dotenv
 
load_dotenv()
 
from db import init_db, init_sentiment_table, insert_news, insert_technicals, insert_tweets, technicals_fetched_today
from config import TICKERS, PAIRS
from layer1.scrapers import fetch_google_news, compute_technicals, fetch_twitter
from layer2.sentiment import run_sentiment_analysis
from layer4.db_layer4 import init_layer4_tables, resolve_pending_paper_trades
from layer4.signals import run_signal_generation
from layer4.similarity import run_similarity_engine
from notifications import notify
from pair_monitor import run_pair_monitor
from telegram_notify import notify_telegram_with_forex
from forex_signals import get_forex_signals
from forex_paper import open_forex_paper_trades, resolve_forex_paper_trades
 
INTERVAL = int(os.environ.get("FETCH_INTERVAL_HOURS", 6))
 
 
def run_pipeline():
    print(f"\n{'='*60}")
    print(f"PIPELINE RUN at {datetime.utcnow().isoformat()}")
    print(f"{'='*60}")
 
    # LAYER 1
    print("\n[LAYER 1] Data Ingestion")
    tech_data = {}
    for ticker in TICKERS:
        print(f"\n  [->] {ticker}")
        news = fetch_google_news(ticker)
        inserted = insert_news(news)
        print(f"      News: {inserted} new items (fetched {len(news)})")
 
        if technicals_fetched_today(ticker):
            print(f"      Technicals: skipped (already fetched today)")
            from db import get_connection
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT rsi, macd_signal, sma20_signal FROM technicals
                WHERE ticker=%s AND error IS NULL
                ORDER BY fetched_at DESC LIMIT 1
            """, (ticker,))
            row = cur.fetchone()
            cur.close(); conn.close()
            if row:
                tech_data[ticker] = {"rsi": float(row[0]) if row[0] else None,
                                     "macd_signal": row[1], "sma20_signal": row[2]}
        else:
            tech = compute_technicals(ticker)
            insert_technicals(tech)
            print(f"      Technicals: RSI={tech.get('rsi','N/A')} | MACD={tech.get('macd_signal','N/A')}")
            tech_data[ticker] = tech
 
        tweets = fetch_twitter(ticker)
        insert_tweets(tweets)
        print(f"      Tweets: {len(tweets)}")
 
    # LAYER 2
    print("\n[LAYER 2] Sentiment Analysis")
    sentiment_results = run_sentiment_analysis() or []
    if sentiment_results:
        print("\n-- SENTIMENT --")
        for r in sentiment_results:
            bar = "^" if r["signal"] == "bullish" else ("v" if r["signal"] == "bearish" else "-")
            print(f"  {bar} {r['ticker']:12} {r['signal'].upper():8} score={r['score']:+.3f}")
 
    # LAYER 4.5
    print("\n[LAYER 4.5] Similarity Engine")
    run_similarity_engine(tech_data)
 
    # LAYER 4
    print("\n[LAYER 4] Pair Signal Generation")
    signal_results = run_signal_generation() or []
 
    # FINAL SUMMARY
    print(f"\n{'='*60}")
    print("FINAL SIGNALS")
    print(f"{'='*60}")
    for r in signal_results:
        hc = " *** HIGH CONFIDENCE ***" if r.get("high_confidence") else ""
        arrow = f"LONG {r['ticker_a']}" if r["signal"] == "long_a" else \
                (f"LONG {r['ticker_b']}" if r["signal"] == "long_b" else "NEUTRAL")
        print(f"  {r['pair']:30} -> {arrow:22} conf={r['confidence']:.2f}{hc}")
 
    # PAIR MONITOR
    try:
        run_pair_monitor()
    except Exception as e:
        print(f"    [Pair Monitor] Error (non-fatal): {e}")
 
    # NOTIFICATIONS + FOREX PAPER TRADING
    print("\n[NOTIFY]")
    resolved = resolve_pending_paper_trades()
    notify(sentiment_results, signal_results, resolved_trades=resolved)
    notify_telegram_with_forex(sentiment_results, signal_results, resolved_trades=resolved)
 
    # Forex paper trading
    try:
        forex_sigs = get_forex_signals(signal_results) if signal_results else []
        opened = open_forex_paper_trades(forex_sigs)
        forex_resolved = resolve_forex_paper_trades()
        if forex_resolved:
            print(f"    [Forex Paper] {forex_resolved} trade(s) resolved")
    except Exception as e:
        print(f"    [Forex Paper] Error (non-fatal): {e}")
 
    print(f"\n[OK] Pipeline complete. Next run in {INTERVAL} hours.")
 
 
if __name__ == "__main__":
    print("market-signal-aggregator starting...")
    print(f"Tickers: {TICKERS}")
    print(f"Interval: every {INTERVAL} hours")
 
    init_db()
    init_sentiment_table()
    init_layer4_tables()
 
    run_pipeline()
 
    schedule.every(INTERVAL).hours.do(run_pipeline)
 
    while True:
        schedule.run_pending()
        time.sleep(60)