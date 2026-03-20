"""
Layer 7: Dynamic Pair Activation/Deactivation
- Evaluates rolling accuracy of each pair (last 20 trades)
- Disables pairs below 45% accuracy
- Reactivates pairs that recover above 55% accuracy
- Runs after each pipeline cycle
"""
 
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_connection
from config import PAIRS
 
MIN_TRADES          = 20    # minimum trades before evaluating
MIN_ACCURACY        = 0.55  # reactivate if >= 55%
MAX_ACCURACY_TO_KEEP = 0.45 # disable if < 45%
 
 
def init_disabled_pairs_table():
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS disabled_pairs (
            pair_name   VARCHAR(100) PRIMARY KEY,
            disabled_at TIMESTAMP DEFAULT NOW(),
            reason      VARCHAR(200)
        )
    """)
    conn.commit(); cur.close(); conn.close()
 
 
def get_disabled_pairs() -> set:
    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("SELECT pair_name FROM disabled_pairs")
        rows = cur.fetchall()
        cur.close(); conn.close()
        return {r[0] for r in rows}
    except Exception:
        cur.close(); conn.close()
        return set()
 
 
def get_pair_rolling_accuracy(pair_name: str) -> dict:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT pt.outcome
        FROM paper_trades pt
        JOIN pair_signals ps ON pt.pair_signal_id = ps.id
        WHERE ps.pair_name = %s AND pt.resolved = TRUE
        ORDER BY pt.opened_at DESC LIMIT %s
    """, (pair_name, MIN_TRADES))
    rows = cur.fetchall()
    cur.close(); conn.close()
 
    if len(rows) < MIN_TRADES:
        return {"pair": pair_name, "trades": len(rows), "accuracy": None}
 
    wins = sum(1 for r in rows if r[0] == "win")
    acc  = round(wins / len(rows), 3)
    return {"pair": pair_name, "trades": len(rows), "accuracy": acc}
 
 
def run_pair_monitor():
    print(f"\n[Pair Monitor] Evaluating pair accuracy...")
    init_disabled_pairs_table()
 
    conn     = get_connection()
    cur      = conn.cursor()
    disabled = get_disabled_pairs()
    changes  = []
 
    for pair in PAIRS:
        name   = pair["name"]
        result = get_pair_rolling_accuracy(name)
 
        if result["accuracy"] is None:
            print(f"    [pending ] {name}: {result['trades']}/{MIN_TRADES} trades")
            continue
 
        acc = result["accuracy"]
 
        if acc < MAX_ACCURACY_TO_KEEP and name not in disabled:
            cur.execute("""
                INSERT INTO disabled_pairs (pair_name, reason)
                VALUES (%s, %s) ON CONFLICT DO NOTHING
            """, (name, f"accuracy {acc*100:.1f}% < {MAX_ACCURACY_TO_KEEP*100:.0f}%"))
            print(f"    [DISABLED] {name}: {acc*100:.1f}% — too low")
            changes.append(f"Disabled: {name} ({acc*100:.1f}%)")
 
        elif acc >= MIN_ACCURACY and name in disabled:
            cur.execute("DELETE FROM disabled_pairs WHERE pair_name=%s", (name,))
            print(f"    [REACTIV ] {name}: {acc*100:.1f}% — recovered")
            changes.append(f"Reactivated: {name} ({acc*100:.1f}%)")
 
        else:
            status = "disabled" if name in disabled else "active  "
            print(f"    [{status}] {name}: {acc*100:.1f}% ({result['trades']} trades)")
 
    conn.commit(); cur.close(); conn.close()
    return changes
 
 
if __name__ == "__main__":
    run_pair_monitor()