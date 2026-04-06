"""
Layer 4 DB helpers — creates and manages:
  - pair_signals       : final bull/bear signal per pair
  - paper_trades       : simulated trade execution
  - source_reputation  : per-domain precision tracking
  - similarity_corpus  : historical setups for matching
"""
 
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_connection
 
 
def init_layer4_tables():
    conn = get_connection()
    cur = conn.cursor()
 
    # ── Pair signals ──────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pair_signals (
            id              SERIAL PRIMARY KEY,
            pair_name       TEXT NOT NULL,
            ticker_a        TEXT NOT NULL,
            ticker_b        TEXT NOT NULL,
            signal          TEXT NOT NULL,  -- long_a | long_b | neutral
            confidence      NUMERIC,        -- 0-1
            sentiment_a     NUMERIC,
            sentiment_b     NUMERIC,
            rsi_a           NUMERIC,
            rsi_b           NUMERIC,
            similarity_score NUMERIC,       -- from layer 4.5
            sources_used    INTEGER,
            created_at      TIMESTAMP DEFAULT NOW()
        );
    """)
 
    # ── Paper trades ──────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS paper_trades (
            id              SERIAL PRIMARY KEY,
            pair_signal_id  INTEGER REFERENCES pair_signals(id),
            ticker          TEXT NOT NULL,
            direction       TEXT NOT NULL,   -- long | short
            entry_price     NUMERIC,
            exit_price      NUMERIC,
            entry_date      TIMESTAMP DEFAULT NOW(),
            is_forward_test BOOLEAN DEFAULT FALSE,
            exit_date       TIMESTAMP,
            pnl_pct         NUMERIC,         -- % gain/loss
            outcome         TEXT,            -- win | loss | pending
            resolved        BOOLEAN DEFAULT FALSE
        );
    """)
 
    # ── Source reputation ─────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS source_reputation (
            id              SERIAL PRIMARY KEY,
            domain          TEXT NOT NULL,
            ticker          TEXT NOT NULL,
            article_title   TEXT,
            predicted_signal TEXT,          -- bullish | bearish | neutral
            article_date    TIMESTAMP,
            resolved        BOOLEAN DEFAULT FALSE,
            was_correct     BOOLEAN,
            correct_count   INTEGER DEFAULT 0,
            total_count     INTEGER DEFAULT 0,
            precision_score NUMERIC,        -- correct / total
            week_number     INTEGER,        -- for 25-week pruning
            created_at      TIMESTAMP DEFAULT NOW(),
            UNIQUE(domain, ticker, article_title)
        );
    """)
 
    # ── Similarity corpus ─────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS similarity_corpus (
            id              SERIAL PRIMARY KEY,
            ticker          TEXT NOT NULL,
            date            DATE NOT NULL,
            rsi             NUMERIC,
            macd_signal     TEXT,
            sma20_signal    TEXT,
            volume_zscore   NUMERIC,        -- volume vs 20d avg
            price_change_5d NUMERIC,        -- % change next 5 days
            pair_outperform BOOLEAN,        -- outperformed pair partner?
            rsi_bounce      BOOLEAN,        -- oversold + bounced?
            is_successful   BOOLEAN,        -- majority vote of 3 definitions
            success_votes   INTEGER,        -- 0-3
            data_source     TEXT DEFAULT 'yahoo_finance',
            created_at      TIMESTAMP DEFAULT NOW(),
            UNIQUE(ticker, date)
        );
    """)
 
    conn.commit()
    cur.close()
    conn.close()
    print("[DB] Layer 4 tables ready.")
 
 
def save_pair_signal(pair_name, ticker_a, ticker_b, signal, confidence,
                     sentiment_a, sentiment_b, rsi_a, rsi_b,
                     similarity_score, sources_used):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO pair_signals
            (pair_name, ticker_a, ticker_b, signal, confidence,
             sentiment_a, sentiment_b, rsi_a, rsi_b,
             similarity_score, sources_used)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING id
    """, (pair_name, ticker_a, ticker_b, signal, confidence,
          sentiment_a, sentiment_b, rsi_a, rsi_b,
          similarity_score, sources_used))
    row = cur.fetchone()
    conn.commit(); cur.close(); conn.close()
    return row[0] if row else None
 
 
def save_paper_trade(pair_signal_id, ticker, direction, entry_price):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO paper_trades (pair_signal_id, ticker, direction, entry_price, is_forward_test)
        VALUES (%s, %s, %s, %s, (NOW() >= '2026-04-06')::BOOLEAN) RETURNING id
    """, (pair_signal_id, ticker, direction, entry_price))
    row = cur.fetchone()
    conn.commit(); cur.close(); conn.close()
    return row[0] if row else None
 
 
def resolve_pending_paper_trades():
    """Check paper trades opened 5 days ago and resolve them."""
    import yfinance as yf
    from datetime import datetime, timedelta
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, ticker, direction, entry_price, entry_date
        FROM paper_trades
        WHERE resolved = FALSE
          AND entry_date <= NOW() - INTERVAL '5 days'
    """)
    rows = cur.fetchall()
    # Batch fetch prices to avoid rate limiting
    import time
    unique_tickers = list(set(r[1] for r in rows))
    yahoo_map = {"CNEC.CN": "CNE.TO"}
    price_cache = {}
    for ticker in unique_tickers:
        symbol = yahoo_map.get(ticker, ticker)
        try:
            hist = yf.Ticker(symbol).history(period="10d")
            if not hist.empty:
                price_cache[ticker] = float(hist["Close"].iloc[-1])
            time.sleep(0.3)  # avoid rate limiting
        except Exception:
            pass
 
    resolved = 0
    for row in rows:
        trade_id, ticker, direction, entry_price, entry_date = row
        try:
            if ticker not in price_cache:
                continue
            exit_price = price_cache[ticker]
            if entry_price and entry_price > 0:
                pnl = ((exit_price - float(entry_price)) / float(entry_price)) * 100
                if direction == "short":
                    pnl = -pnl
                outcome = "win" if pnl > 0 else "loss"
                cur.execute("""
                    UPDATE paper_trades
                    SET exit_price=%s, exit_date=NOW(), pnl_pct=%s,
                        outcome=%s, resolved=TRUE
                    WHERE id=%s
                """, (exit_price, pnl, outcome, trade_id))
                resolved += 1
        except Exception as e:
            print(f"    [Paper] Error resolving trade {trade_id}: {e}")
    conn.commit(); cur.close(); conn.close()
    return resolved
 
 
def upsert_source_reputation(domain, ticker, article_title, predicted_signal, week_number):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO source_reputation
            (domain, ticker, article_title, predicted_signal, week_number)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (domain, ticker, article_title) DO NOTHING
    """, (domain, ticker, article_title, predicted_signal, week_number))
    conn.commit(); cur.close(); conn.close()
 
 
def prune_worst_sources(min_weeks=25, prune_pct=0.10):
    """After 25 weeks, remove bottom decile of sources by precision."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT domain, ticker, 
               SUM(CASE WHEN was_correct THEN 1 ELSE 0 END)::FLOAT / NULLIF(COUNT(*),0) as precision,
               COUNT(*) as total
        FROM source_reputation
        WHERE resolved = TRUE
        GROUP BY domain, ticker
        HAVING MAX(week_number) >= %s AND COUNT(*) >= 5
        ORDER BY precision ASC
    """, (min_weeks,))
    rows = cur.fetchall()
    if not rows:
        cur.close(); conn.close()
        return 0
    cutoff = int(len(rows) * prune_pct)
    pruned = 0
    for domain, ticker, precision, total in rows[:cutoff]:
        cur.execute("""
            DELETE FROM source_reputation WHERE domain=%s AND ticker=%s
        """, (domain, ticker))
        print(f"    [Prune] Removed {domain} for {ticker} (precision={precision:.2f}, n={total})")
        pruned += 1
    conn.commit(); cur.close(); conn.close()
    return pruned