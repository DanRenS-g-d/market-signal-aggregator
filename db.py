import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    return psycopg2.connect(os.environ["DATABASE_URL"])

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS news (
            id          SERIAL PRIMARY KEY,
            ticker      TEXT NOT NULL,
            title       TEXT,
            summary     TEXT,
            link        TEXT,
            published   TEXT,
            fetched_at  TIMESTAMP DEFAULT NOW()
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS technicals (
            id              SERIAL PRIMARY KEY,
            ticker          TEXT NOT NULL,
            price           NUMERIC,
            rsi             NUMERIC,
            rsi_signal      TEXT,
            macd_signal     TEXT,
            sma20_signal    TEXT,
            volume_signal   TEXT,
            error           TEXT,
            fetched_at      TIMESTAMP DEFAULT NOW()
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tweets (
            id          SERIAL PRIMARY KEY,
            ticker      TEXT NOT NULL,
            text        TEXT,
            created_at  TEXT,
            likes       INTEGER,
            retweets    INTEGER,
            fetched_at  TIMESTAMP DEFAULT NOW()
        );
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("[DB] Tables ready.")


def init_sentiment_table():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sentiment (
            id              SERIAL PRIMARY KEY,
            ticker          TEXT NOT NULL,
            signal          TEXT,
            score           NUMERIC,
            avg_positive    NUMERIC,
            avg_negative    NUMERIC,
            avg_neutral     NUMERIC,
            article_count   INTEGER,
            analyzed_at     TIMESTAMP DEFAULT NOW()
        );
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("[DB] Sentiment table ready.")


def insert_news(items: list[dict]):
    """Insert news, skipping duplicates by title+ticker."""
    if not items:
        return 0
    conn = get_connection()
    cur = conn.cursor()
    inserted = 0
    for item in items:
        cur.execute(
            "SELECT id FROM news WHERE ticker = %s AND title = %s LIMIT 1",
            (item.get("ticker"), item.get("title"))
        )
        if cur.fetchone():
            continue
        cur.execute("""
            INSERT INTO news (ticker, title, summary, link, published)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            item.get("ticker"),
            item.get("title"),
            item.get("summary"),
            item.get("link"),
            item.get("published"),
        ))
        inserted += 1
    conn.commit()
    cur.close()
    conn.close()
    return inserted


def technicals_fetched_today(ticker: str) -> bool:
    """Returns True if technicals were already fetched in the last 20 hours."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id FROM technicals
        WHERE ticker = %s
          AND fetched_at >= NOW() - INTERVAL '20 hours'
          AND error IS NULL
        LIMIT 1
    """, (ticker,))
    result = cur.fetchone()
    cur.close()
    conn.close()
    return result is not None


def insert_technicals(item: dict):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO technicals
            (ticker, price, rsi, rsi_signal, macd_signal, sma20_signal, volume_signal, error)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        item.get("ticker"),
        item.get("price"),
        item.get("rsi"),
        item.get("rsi_signal"),
        item.get("macd_signal"),
        item.get("sma20_signal"),
        item.get("volume_signal"),
        item.get("error"),
    ))
    conn.commit()
    cur.close()
    conn.close()


def insert_tweets(items: list[dict]):
    if not items:
        return
    conn = get_connection()
    cur = conn.cursor()
    for item in items:
        cur.execute("""
            INSERT INTO tweets (ticker, text, created_at, likes, retweets)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            item.get("ticker"),
            item.get("text"),
            item.get("created_at"),
            item.get("likes", 0),
            item.get("retweets", 0),
        ))
    conn.commit()
    cur.close()
    conn.close()