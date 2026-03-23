"""
Formal Backtesting Module — v2
Fixes:
- Sharpe uses actual trading days, not invented annualization
- Walk-forward validation (train 70% / test 30%)
- Confidence calibration check
- Per-pair regime analysis
"""
 
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_connection
from datetime import datetime
 
 
def get_resolved_trades() -> list:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT
            pt.id, ps.pair_name, ps.ticker_a, ps.ticker_b,
            ps.signal, ps.confidence,
            pt.entry_price, pt.exit_price, pt.pnl_pct,
            pt.outcome, pt.entry_date, pt.exit_date
        FROM paper_trades pt
        JOIN pair_signals ps ON pt.pair_signal_id = ps.id
        WHERE pt.resolved = TRUE
        ORDER BY pt.entry_date ASC
    """)
    cols = ["id","pair","ticker_a","ticker_b","signal","confidence",
            "entry_price","exit_price","pnl_pct","outcome","entry_date","exit_date"]
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [dict(zip(cols, r)) for r in rows]
 
 
def calculate_sharpe(pnls: list, actual_days: int) -> float:
    """
    Correct Sharpe: annualize based on actual calendar days observed,
    not an assumed number of trades per year.
    """
    if not pnls or actual_days <= 0:
        return 0.0
    n = len(pnls)
    # Daily risk-free rate (Fed funds ~4.5% annual)
    rf_annual   = 4.5
    rf_per_trade = rf_annual / (365 / (actual_days / n))
    excess      = [p - rf_per_trade for p in pnls]
    mean_e      = sum(excess) / n
    variance    = sum((r - mean_e) ** 2 for r in excess) / n
    std         = math.sqrt(variance) if variance > 0 else 0.0001
    # Annualization factor based on actual frequency
    trades_per_year = n / (actual_days / 365)
    return round((mean_e / std) * math.sqrt(trades_per_year), 3)
 
 
def calculate_max_drawdown(pnls: list) -> float:
    peak = running = 0.0
    max_dd = 0.0
    for p in pnls:
        running += p
        if running > peak:
            peak = running
        dd = peak - running
        if dd > max_dd:
            max_dd = dd
    return round(max_dd, 3)
 
 
def max_consecutive(pnls: list, positive: bool) -> int:
    max_streak = current = 0
    for p in pnls:
        if (positive and p > 0) or (not positive and p <= 0):
            current += 1
            max_streak = max(max_streak, current)
        else:
            current = 0
    return max_streak
 
 
def walk_forward_validation(trades: list) -> dict:
    """
    Split trades 70/30 train/test.
    Checks if accuracy holds out-of-sample.
    This is the key overfitting test.
    """
    n      = len(trades)
    split  = int(n * 0.7)
    train  = trades[:split]
    test   = trades[split:]
 
    def acc(t):
        wins = [x for x in t if x["outcome"] == "win"]
        return round(len(wins) / len(t), 3) if t else 0
 
    def avg_pnl(t):
        pnls = [float(x["pnl_pct"]) for x in t if x["pnl_pct"]]
        return round(sum(pnls) / len(pnls), 3) if pnls else 0
 
    train_acc = acc(train)
    test_acc  = acc(test)
    degradation = round(train_acc - test_acc, 3)
 
    return {
        "train_n":     len(train),
        "test_n":      len(test),
        "train_acc":   train_acc,
        "test_acc":    test_acc,
        "train_pnl":   avg_pnl(train),
        "test_pnl":    avg_pnl(test),
        "degradation": degradation,
        "overfit_risk": "HIGH" if degradation > 0.15 else
                        ("MEDIUM" if degradation > 0.07 else "LOW"),
    }
 
 
def confidence_calibration(trades: list) -> dict:
    """
    Check if higher confidence actually predicts better outcomes.
    If high confidence loses more than low confidence → miscalibration.
    """
    bins = {
        "low (<0.50)":    [],
        "mid (0.50-0.74)":[],
        "high (>=0.75)":  [],
    }
    for t in trades:
        conf = float(t["confidence"]) if t["confidence"] else 0
        pnl  = float(t["pnl_pct"]) if t["pnl_pct"] else 0
        if conf >= 0.75:
            bins["high (>=0.75)"].append(pnl)
        elif conf >= 0.50:
            bins["mid (0.50-0.74)"].append(pnl)
        else:
            bins["low (<0.50)"].append(pnl)
 
    result = {}
    for tier, pnls in bins.items():
        if pnls:
            wins = [p for p in pnls if p > 0]
            result[tier] = {
                "n":        len(pnls),
                "win_rate": round(len(wins) / len(pnls), 3),
                "avg_pnl":  round(sum(pnls) / len(pnls), 3),
            }
 
    # Check monotonicity — higher conf should mean higher win rate
    tiers   = ["low (<0.50)", "mid (0.50-0.74)", "high (>=0.75)"]
    rates   = [result.get(t, {}).get("win_rate", 0) for t in tiers]
    is_monotonic = rates[0] <= rates[1] <= rates[2]
 
    result["calibrated"] = is_monotonic
    result["verdict"]    = "✅ Calibrated" if is_monotonic else "❌ Miscalibrated — high conf does NOT predict better outcomes"
    return result
 
 
def pair_regime_analysis(trades: list) -> dict:
    """
    Per-pair analysis with regime detection.
    Flags pairs that only work in specific market conditions.
    """
    pairs = {}
    for t in trades:
        pair = t["pair"]
        if pair not in pairs:
            pairs[pair] = []
        if t["pnl_pct"]:
            pairs[pair].append({
                "pnl":  float(t["pnl_pct"]),
                "date": t["entry_date"],
                "win":  t["outcome"] == "win"
            })
 
    result = {}
    for pair, data in pairs.items():
        n    = len(data)
        wins = [d for d in data if d["win"]]
        pnls = [d["pnl"] for d in data]
        acc  = round(len(wins) / n, 3) if n > 0 else 0
 
        # Streak analysis — detect if wins are clustered (regime-dependent)
        win_streak = max_consecutive(pnls, positive=True)
        loss_streak = max_consecutive(pnls, positive=False)
 
        # Flag potential issues
        flags = []
        if acc == 1.0 and n < 30:
            flags.append("⚠️ 100% acc with <30 trades — insufficient data")
        if acc == 1.0 and n >= 30:
            flags.append("⚠️ 100% acc — possible look-ahead bias or regime dependency")
        if win_streak > n * 0.6:
            flags.append(f"⚠️ {win_streak} consecutive wins — possible regime clustering")
        if acc < 0.45:
            flags.append("❌ Below threshold — should be disabled")
        if n < 10:
            flags.append("⏳ Insufficient data (<10 trades)")
 
        result[pair] = {
            "n":           n,
            "accuracy":    acc,
            "avg_pnl":     round(sum(pnls) / n, 3) if pnls else 0,
            "max_win_streak":  win_streak,
            "max_loss_streak": loss_streak,
            "flags":       flags,
        }
 
    return result
 
 
def print_backtest_report(trades: list):
    if not trades:
        print("No resolved trades yet.")
        return
 
    pnls = [float(t["pnl_pct"]) for t in trades if t["pnl_pct"]]
    n    = len(pnls)
    wins = [p for p in pnls if p > 0]
 
    # Calculate actual days span
    dates = [t["entry_date"] for t in trades if t["entry_date"]]
    if len(dates) >= 2:
        first = min(dates)
        last  = max(dates)
        actual_days = max((last - first).days, 1)
    else:
        actual_days = 30
 
    sharpe  = calculate_sharpe(pnls, actual_days)
    max_dd  = calculate_max_drawdown(pnls)
    wf      = walk_forward_validation(trades)
    calib   = confidence_calibration(trades)
    regimes = pair_regime_analysis(trades)
 
    annual_return = (sum(pnls) / actual_days) * 365
    calmar  = round(annual_return / max_dd, 3) if max_dd > 0 else 0
    gross_profit = sum(wins)
    gross_loss   = abs(sum(p for p in pnls if p <= 0)) or 0.0001
    pf      = round(gross_profit / gross_loss, 3)
 
    print(f"\n{'='*58}")
    print(f"  BACKTEST REPORT v2 — {datetime.utcnow().strftime('%Y-%m-%d')}")
    print(f"  Period: {actual_days} days | {n} trades")
    print(f"{'='*58}")
 
    print(f"\n📊 PERFORMANCE")
    print(f"  Win rate:          {len(wins)/n*100:.1f}%")
    print(f"  Avg P&L/trade:     {sum(pnls)/n:+.2f}%")
    print(f"  Total P&L:         {sum(pnls):+.2f}%")
    print(f"  Annualized return: {annual_return:+.1f}%")
    print(f"  Best/Worst:        {max(pnls):+.2f}% / {min(pnls):+.2f}%")
 
    print(f"\n📈 RISK METRICS (corrected)")
    print(f"  Sharpe ratio:      {sharpe:.3f}  {'✅' if 1 <= sharpe <= 4 else ('⚠️ Suspiciously high — check overfitting' if sharpe > 4 else '❌ Below 1.0')}")
    print(f"  Max drawdown:      -{max_dd:.2f}%")
    print(f"  Calmar ratio:      {calmar:.3f}")
    print(f"  Profit factor:     {pf:.3f}  {'✅' if pf > 1.5 else '⚠️'}")
    print(f"  Max consec wins:   {max_consecutive(pnls, True)}")
    print(f"  Max consec losses: {max_consecutive(pnls, False)}")
 
    print(f"\n🔀 WALK-FORWARD VALIDATION (overfitting test)")
    print(f"  Train ({wf['train_n']} trades): acc={wf['train_acc']*100:.1f}% | avg={wf['train_pnl']:+.2f}%")
    print(f"  Test  ({wf['test_n']} trades):  acc={wf['test_acc']*100:.1f}% | avg={wf['test_pnl']:+.2f}%")
    print(f"  Degradation:       {wf['degradation']*100:.1f}%")
    print(f"  Overfit risk:      {wf['overfit_risk']}")
 
    print(f"\n🎯 CONFIDENCE CALIBRATION")
    for tier, stats in calib.items():
        if isinstance(stats, dict):
            print(f"  {tier}: n={stats['n']} | win={stats['win_rate']*100:.1f}% | avg={stats['avg_pnl']:+.2f}%")
    print(f"  Verdict: {calib.get('verdict', 'N/A')}")
 
    print(f"\n📋 PAIR REGIME ANALYSIS")
    for pair, data in sorted(regimes.items(), key=lambda x: x[1]["avg_pnl"], reverse=True):
        flag_str = " ".join(data["flags"]) if data["flags"] else "✅ OK"
        print(f"  {pair:32} {data['n']:3}t | {data['accuracy']*100:.0f}% | {data['avg_pnl']:+.2f}% | {flag_str}")
 
    print(f"\n🏆 BENCHMARK (annualized)")
    print(f"  This system: {annual_return:+.1f}%")
    print(f"  S&P 500 avg: +10.5%")
    print(f"  VT:          +8.0%")
    if annual_return > 10.5:
        print(f"  ✅ Beating S&P 500")
    print(f"{'='*58}\n")
 
 
def run_backtest():
    trades = get_resolved_trades()
    print_backtest_report(trades)
 
 
if __name__ == "__main__":
    run_backtest()