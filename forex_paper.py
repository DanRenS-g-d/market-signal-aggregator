"""
Forex Paper Trading Module
Tracks forex signals, records entry prices, resolves after 5 days.
Measures accuracy of forex signal translation layer.
"""
 
import os, sys
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_connection
 
 
def init_forex_paper_table():
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS forex_paper_trades (
            id              SERIAL PRIMARY KEY,
            pair            VARCHAR(20) NOT NULL,
            direction       VARCHAR(10) NOT NULL,
            action          VARCHAR(50),
            strength        VARCHAR(10),
            confidence      DECIMAL(5,3),
            source_tickers  TEXT,
            entry_price     DECIMAL(12,6),
            entry_at        TIMESTAMP DEFAULT NOW(),
            exit_price      DECIMAL(12,6),
            exit_at         TIMESTAMP,
            pnl_pct         DECIMAL(8,4),
            outcome         VARCHAR(10),
            resolved        BOOLEAN DEFAULT FALSE
        )
    """)
    conn.commit(); cur.close(); conn.close()
 
 
def get_forex_price(pair: str) -> float:
    """Get current forex price from yfinance."""
    try:
        import yfinance as yf
        # Convert USD/MXN to USDMXN=X format for yfinance
        base, quote = pair.split("/")
        symbol = f"{base}{quote}=X"
        hist = yf.Ticker(symbol).history(period="1d")
        if not hist.empty:
            return round(float(hist["Close"].iloc[-1]), 6)
    except Exception as e:
        print(f"    [Forex Paper] Price error for {pair}: {e}")
    return 0.0
 
 
def open_forex_paper_trades(forex_signals: list):
    """Open paper trades for new forex signals."""
    if not forex_signals:
        return
 
    init_forex_paper_table()
    conn = get_connection()
    cur  = conn.cursor()
    opened = 0
 
    for sig in forex_signals:
        # Skip weak signals
        if sig["confidence"] < 0.25:
            continue
 
        # Check if we already have an open trade for this pair
        cur.execute("""
            SELECT id FROM forex_paper_trades
            WHERE pair = %s AND resolved = FALSE
            AND entry_at >= NOW() - INTERVAL '6 hours'
        """, (sig["pair"],))
        if cur.fetchone():
            continue
 
        price = get_forex_price(sig["pair"])
        if price <= 0:
            print(f"    [Forex Paper] No price for {sig['pair']} — skipping")
            continue
 
        cur.execute("""
            INSERT INTO forex_paper_trades
                (pair, direction, action, strength, confidence,
                 source_tickers, entry_price)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            sig["pair"], sig["direction"], sig["action"],
            sig["strength"], sig["confidence"],
            ", ".join(sig.get("reasons", [])[:1]),
            price
        ))
        trade_id = cur.fetchone()[0]
        opened += 1
        print(f"    [Forex Paper] Opened trade id={trade_id} | {sig['action']} @ {price}")
 
    conn.commit(); cur.close(); conn.close()
    return opened
 
 
def resolve_forex_paper_trades():
    """Resolve forex paper trades older than 5 days."""
    init_forex_paper_table()
    conn = get_connection()
    cur  = conn.cursor()
 
    cur.execute("""
        SELECT id, pair, direction, entry_price
        FROM forex_paper_trades
        WHERE resolved = FALSE
          AND entry_at <= NOW() - INTERVAL '5 days'
    """)
    trades = cur.fetchall()
 
    resolved = 0
    for trade_id, pair, direction, entry_price in trades:
        exit_price = get_forex_price(pair)
        if exit_price <= 0:
            continue
 
        entry_price = float(entry_price)
        pnl_pct = (exit_price - entry_price) / entry_price * 100
 
        # For short positions, invert the P&L
        if direction == "short":
            pnl_pct = -pnl_pct
 
        outcome = "win" if pnl_pct > 0 else "loss"
 
        cur.execute("""
            UPDATE forex_paper_trades
            SET resolved = TRUE, exit_price = %s, exit_at = NOW(),
                pnl_pct = %s, outcome = %s
            WHERE id = %s
        """, (exit_price, round(pnl_pct, 4), outcome, trade_id))
 
        print(f"    [Forex Paper] Resolved id={trade_id} | {pair} | {outcome} | {pnl_pct:+.2f}%")
        resolved += 1
 
    conn.commit(); cur.close(); conn.close()
    return resolved
 
 
def get_forex_accuracy_report() -> dict:
    """Get accuracy report for forex paper trades."""
    init_forex_paper_table()
    conn = get_connection()
    cur  = conn.cursor()
 
    cur.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN outcome='win' THEN 1 ELSE 0 END) as wins,
            AVG(pnl_pct) as avg_pnl,
            MAX(pnl_pct) as best,
            MIN(pnl_pct) as worst
        FROM forex_paper_trades
        WHERE resolved = TRUE
    """)
    row = cur.fetchone()
    total, wins, avg_pnl, best, worst = row
 
    cur.execute("""
        SELECT pair, COUNT(*) as trades,
               SUM(CASE WHEN outcome='win' THEN 1 ELSE 0 END) as wins,
               AVG(pnl_pct) as avg_pnl
        FROM forex_paper_trades
        WHERE resolved = TRUE
        GROUP BY pair ORDER BY avg_pnl DESC
    """)
    by_pair = cur.fetchall()
 
    cur.execute("SELECT COUNT(*) FROM forex_paper_trades WHERE resolved = FALSE")
    pending = cur.fetchone()[0]
 
    cur.close(); conn.close()
 
    total = total or 0
    wins  = wins  or 0
    acc   = round(wins / total * 100, 1) if total > 0 else 0
 
    print(f"\n{'='*50}")
    print(f"FOREX PAPER TRADING ACCURACY")
    print(f"{'='*50}")
    print(f"Total resolved: {total} | Wins: {wins} | Accuracy: {acc}%")
    print(f"Avg P&L: {round(float(avg_pnl), 2) if avg_pnl else 0:+.2f}%")
    print(f"Pending: {pending}")
    if by_pair:
        print(f"\nBy pair:")
        for p in by_pair:
            pair_acc = round(p[2] / p[1] * 100, 1) if p[1] > 0 else 0
            print(f"  {p[0]:12} {p[1]} trades | {pair_acc}% acc | {round(float(p[3]),2):+.2f}% avg")
 
    return {"total": total, "wins": wins, "accuracy": acc, "pending": pending}
 
 
if __name__ == "__main__":
    get_forex_accuracy_report()