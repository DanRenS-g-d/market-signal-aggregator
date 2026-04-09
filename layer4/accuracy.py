"""
Accuracy tracker — measures if paper trades are beating 55% threshold.
Run after paper trades resolve to get system performance metrics.
"""
 
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_connection
 
 
def get_accuracy_report() -> dict:
    conn = get_connection()
    cur = conn.cursor()
 
    # Overall accuracy
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN outcome='win' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN outcome='loss' THEN 1 ELSE 0 END) as losses,
            AVG(pnl_pct) as avg_pnl,
            MAX(pnl_pct) as best_trade,
            MIN(pnl_pct) as worst_trade
        FROM paper_trades
        WHERE resolved = TRUE
    """)
    row = cur.fetchone()
    total, wins, losses, avg_pnl, best, worst = row
 
    # By pair
    cur.execute("""
        SELECT 
            ps.pair_name,
            COUNT(*) as trades,
            SUM(CASE WHEN pt.outcome='win' THEN 1 ELSE 0 END) as wins,
            AVG(pt.pnl_pct) as avg_pnl
        FROM paper_trades pt
        JOIN pair_signals ps ON pt.pair_signal_id = ps.id
        WHERE pt.resolved = TRUE
        GROUP BY ps.pair_name
        ORDER BY avg_pnl DESC
    """)
    pair_rows = cur.fetchall()
 
    cur.close(); conn.close()
 
    total = total or 0
    wins = wins or 0
    accuracy = round(wins / total * 100, 1) if total > 0 else 0
 
    report = {
        "total_trades": total,
        "wins": wins,
        "losses": losses or 0,
        "accuracy_pct": accuracy,
        "beats_threshold": accuracy >= 55.0,
        "avg_pnl_pct": round(float(avg_pnl), 3) if avg_pnl and not __import__('math').isnan(float(avg_pnl)) else 0,
        "best_trade_pct": round(float(best), 3) if best and not __import__('math').isnan(float(best)) else 0,
        "worst_trade_pct": round(float(worst), 3) if worst and not __import__('math').isnan(float(worst)) else 0,
        "by_pair": [
            {
                "pair": r[0],
                "trades": r[1],
                "wins": r[2],
                "accuracy_pct": round(r[2] / r[1] * 100, 1) if r[1] > 0 else 0,
                "avg_pnl": round(float(r[3]), 3) if r[3] and not __import__('math').isnan(float(r[3])) else 0,
            }
            for r in pair_rows
        ],
        "pending_trades": _count_pending(),
    }
 
    return report
 
 
def _count_pending() -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM paper_trades WHERE resolved = FALSE")
    count = cur.fetchone()[0]
    cur.close(); conn.close()
    return count
 
 
def print_accuracy_report():
    r = get_accuracy_report()
    print(f"\n{'='*50}")
    print(f"ACCURACY REPORT")
    print(f"{'='*50}")
    print(f"Total resolved trades: {r['total_trades']}")
    print(f"Wins: {r['wins']} | Losses: {r['losses']}")
    print(f"Accuracy: {r['accuracy_pct']}% {'✅ BEATS 55% THRESHOLD' if r['beats_threshold'] else '❌ below 55% threshold'}")
    print(f"Avg P&L: {r['avg_pnl_pct']:+.2f}% | Best: {r['best_trade_pct']:+.2f}% | Worst: {r['worst_trade_pct']:+.2f}%")
    print(f"Pending trades: {r['pending_trades']}")
 
    if r['by_pair']:
        print(f"\nBy pair:")
        for p in r['by_pair']:
            print(f"  {p['pair']:30} {p['trades']} trades | {p['accuracy_pct']}% acc | {p['avg_pnl']:+.2f}% avg")
 
    return r
 
 
if __name__ == "__main__":
    print_accuracy_report()