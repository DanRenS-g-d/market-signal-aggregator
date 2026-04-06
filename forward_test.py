"""
Forward Test Framework
Tags all paper trades opened after ABLATION_DATE as forward test trades.
Tracks them separately from historical backtest data.
Run this once to tag existing trades, then it auto-tags new ones.
"""
 
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_connection
from datetime import datetime, date
 
# Date of ablation — all trades AFTER this are forward test
ABLATION_DATE = "2026-04-06"
 
 
def init_forward_test_column():
    """Add is_forward_test column to paper_trades if not exists."""
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("""
            ALTER TABLE paper_trades
            ADD COLUMN IF NOT EXISTS is_forward_test BOOLEAN DEFAULT FALSE
        """)
        conn.commit()
        print("    [Forward Test] Column added/verified")
    except Exception as e:
        print(f"    [Forward Test] Column error: {e}")
    cur.close(); conn.close()
 
 
def tag_existing_trades():
    """
    Tag all existing trades as backtest (before ablation date)
    or forward test (after ablation date).
    Run once after ablation.
    """
    conn = get_connection()
    cur  = conn.cursor()
 
    # Tag pre-ablation as backtest
    cur.execute("""
        UPDATE paper_trades
        SET is_forward_test = FALSE
        WHERE entry_date < %s
    """, (ABLATION_DATE,))
    backtest_count = cur.rowcount
 
    # Tag post-ablation as forward test
    cur.execute("""
        UPDATE paper_trades
        SET is_forward_test = TRUE
        WHERE entry_date >= %s
    """, (ABLATION_DATE,))
    forward_count = cur.rowcount
 
    conn.commit(); cur.close(); conn.close()
    print(f"    [Forward Test] Tagged {backtest_count} backtest trades, {forward_count} forward test trades")
    return backtest_count, forward_count
 
 
def get_forward_test_report() -> dict:
    """Get accuracy report for forward test trades only."""
    conn = get_connection()
    cur  = conn.cursor()
 
    # Overall forward test stats
    cur.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN outcome='win' THEN 1 ELSE 0 END) as wins,
            AVG(pnl_pct) as avg_pnl,
            MAX(pnl_pct) as best,
            MIN(pnl_pct) as worst
        FROM paper_trades
        WHERE is_forward_test = TRUE AND resolved = TRUE
    """)
    row = cur.fetchone()
    total, wins, avg_pnl, best, worst = row
    total = total or 0
    wins  = wins  or 0
 
    # Pending forward test trades
    cur.execute("""
        SELECT COUNT(*) FROM paper_trades
        WHERE is_forward_test = TRUE AND resolved = FALSE
    """)
    pending = cur.fetchone()[0]
 
    # By pair — forward test only
    cur.execute("""
        SELECT ps.pair_name,
               COUNT(*) as n,
               SUM(CASE WHEN pt.outcome='win' THEN 1 ELSE 0 END) as wins,
               AVG(pt.pnl_pct) as avg_pnl
        FROM paper_trades pt
        JOIN pair_signals ps ON pt.pair_signal_id = ps.id
        WHERE pt.is_forward_test = TRUE AND pt.resolved = TRUE
        GROUP BY ps.pair_name
        ORDER BY AVG(pt.pnl_pct) DESC
    """)
    by_pair = cur.fetchall()
 
    # Compare backtest vs forward test accuracy
    cur.execute("""
        SELECT
            is_forward_test,
            COUNT(*) as total,
            SUM(CASE WHEN outcome='win' THEN 1 ELSE 0 END) as wins,
            AVG(pnl_pct) as avg_pnl
        FROM paper_trades
        WHERE resolved = TRUE
        GROUP BY is_forward_test
    """)
    comparison = cur.fetchall()
 
    cur.close(); conn.close()
 
    acc = round(wins / total * 100, 1) if total > 0 else 0
 
    print(f"\n{'='*55}")
    print(f"  FORWARD TEST REPORT")
    print(f"  Ablation date: {ABLATION_DATE}")
    print(f"{'='*55}")
 
    print(f"\n📊 FORWARD TEST (out-of-sample)")
    print(f"  Resolved trades: {total}")
    print(f"  Pending trades:  {pending}")
    print(f"  Accuracy:        {acc}%")
    if avg_pnl:
        print(f"  Avg P&L:         {float(avg_pnl):+.2f}%")
    if best and worst:
        print(f"  Best / Worst:    {float(best):+.2f}% / {float(worst):+.2f}%")
 
    print(f"\n🔀 BACKTEST vs FORWARD TEST")
    for row in comparison:
        label = "Forward test" if row[0] else "Backtest    "
        n     = row[1]
        w     = row[2] or 0
        pnl   = float(row[3]) if row[3] else 0
        a     = round(w / n * 100, 1) if n > 0 else 0
        print(f"  {label}: {n:3} trades | {a:.1f}% acc | {pnl:+.2f}% avg")
 
    if total >= 20:
        backtest_acc = next((round(r[2]/r[1]*100,1) for r in comparison if not r[0]), 0)
        degradation  = backtest_acc - acc
        print(f"\n  Degradation: {degradation:+.1f}%")
        if degradation < 5:
            print(f"  Verdict: LOW overfitting risk — system generalizes")
        elif degradation < 15:
            print(f"  Verdict: MEDIUM risk — monitor closely")
        else:
            print(f"  Verdict: HIGH overfitting — system may not generalize")
    else:
        print(f"\n  Need {20 - total} more resolved forward test trades for verdict")
 
    if by_pair:
        print(f"\n📋 BY PAIR (forward test only)")
        for p in by_pair:
            pair_acc = round(float(p[2]) / float(p[1]) * 100, 1) if p[1] > 0 else 0
            pnl      = float(p[3]) if p[3] else 0
            flag     = "✅" if pair_acc >= 60 else ("⚠️" if pair_acc >= 45 else "❌")
            print(f"  {flag} {p[0]:32} {p[1]:2}t | {pair_acc:.0f}% | {pnl:+.2f}%")
 
    print(f"{'='*55}\n")
 
    return {
        "total":    total,
        "pending":  pending,
        "accuracy": acc,
        "avg_pnl":  float(avg_pnl) if avg_pnl else 0,
    }
 
 
def setup_forward_test():
    """Run once to initialize forward test framework."""
    print("[Forward Test] Setting up framework...")
    init_forward_test_column()
    tag_existing_trades()
    print("[Forward Test] Setup complete. All new trades will be auto-tagged.")
 
 
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        setup_forward_test()
    else:
        get_forward_test_report()