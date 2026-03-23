"""
Formal Backtesting Module
Calculates Sharpe ratio, max drawdown, Calmar ratio, win rate,
profit factor, and other institutional metrics from paper trading history.
"""
 
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_connection
from datetime import datetime
 
 
def get_resolved_trades() -> list:
    """Fetch all resolved paper trades from DB."""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT
            pt.id,
            ps.pair_name,
            ps.ticker_a,
            ps.ticker_b,
            ps.signal,
            ps.confidence,
            pt.entry_price,
            pt.exit_price,
            pt.pnl_pct,
            pt.outcome,
            pt.entry_date,
            pt.exit_date
        FROM paper_trades pt
        JOIN pair_signals ps ON pt.pair_signal_id = ps.id
        WHERE pt.resolved = TRUE
        ORDER BY pt.entry_date ASC
    """)
    cols = ["id", "pair", "ticker_a", "ticker_b", "signal",
            "confidence", "entry_price", "exit_price", "pnl_pct",
            "outcome", "entry_date", "exit_date"]
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [dict(zip(cols, r)) for r in rows]
 
 
def calculate_metrics(trades: list) -> dict:
    """Calculate all institutional backtesting metrics."""
    import math
 
    if not trades:
        return {}
 
    pnls = [float(t["pnl_pct"]) for t in trades if t["pnl_pct"] is not None]
    if not pnls:
        return {}
 
    n         = len(pnls)
    wins      = [p for p in pnls if p > 0]
    losses    = [p for p in pnls if p <= 0]
    win_rate  = len(wins) / n
 
    # ── Basic stats ───────────────────────────────────────────
    avg_pnl   = sum(pnls) / n
    avg_win   = sum(wins) / len(wins) if wins else 0
    avg_loss  = sum(losses) / len(losses) if losses else 0
    best      = max(pnls)
    worst     = min(pnls)
    total_pnl = sum(pnls)
 
    # ── Sharpe Ratio ──────────────────────────────────────────
    # Annualized: assume ~4 trades/week (6h interval) = ~208 trades/year
    # Risk-free rate: 4.5% annual = 0.0217% per trade
    RISK_FREE_PER_TRADE = 4.5 / 208
    excess_returns = [p - RISK_FREE_PER_TRADE for p in pnls]
    mean_excess    = sum(excess_returns) / n
    variance       = sum((r - mean_excess) ** 2 for r in excess_returns) / n
    std_dev        = math.sqrt(variance) if variance > 0 else 0.0001
    sharpe         = round((mean_excess / std_dev) * math.sqrt(208), 3) if std_dev > 0 else 0
 
    # ── Max Drawdown ──────────────────────────────────────────
    cumulative = []
    running    = 0
    for p in pnls:
        running += p
        cumulative.append(running)
 
    peak        = cumulative[0]
    max_dd      = 0
    for val in cumulative:
        if val > peak:
            peak = val
        dd = peak - val
        if dd > max_dd:
            max_dd = dd
 
    # ── Calmar Ratio ──────────────────────────────────────────
    # Annualized return / max drawdown
    annual_return = avg_pnl * 208
    calmar        = round(annual_return / max_dd, 3) if max_dd > 0 else 0
 
    # ── Profit Factor ─────────────────────────────────────────
    gross_profit = sum(wins) if wins else 0
    gross_loss   = abs(sum(losses)) if losses else 0.0001
    profit_factor = round(gross_profit / gross_loss, 3)
 
    # ── Sortino Ratio ─────────────────────────────────────────
    # Like Sharpe but only penalizes downside volatility
    downside = [p for p in excess_returns if p < 0]
    down_var  = sum(r ** 2 for r in downside) / n if downside else 0.0001
    down_std  = math.sqrt(down_var)
    sortino   = round((mean_excess / down_std) * math.sqrt(208), 3) if down_std > 0 else 0
 
    # ── Consecutive stats ─────────────────────────────────────
    max_consec_wins   = max_consecutive(pnls, positive=True)
    max_consec_losses = max_consecutive(pnls, positive=False)
 
    # ── By confidence tier ────────────────────────────────────
    by_conf = {}
    for t in trades:
        conf = float(t["confidence"]) if t["confidence"] else 0
        tier = "high (>=0.75)" if conf >= 0.75 else ("mid (0.50-0.74)" if conf >= 0.50 else "low (<0.50)")
        if tier not in by_conf:
            by_conf[tier] = []
        if t["pnl_pct"]:
            by_conf[tier].append(float(t["pnl_pct"]))
 
    conf_stats = {}
    for tier, tier_pnls in by_conf.items():
        if tier_pnls:
            conf_stats[tier] = {
                "trades":   len(tier_pnls),
                "win_rate": round(len([p for p in tier_pnls if p > 0]) / len(tier_pnls), 3),
                "avg_pnl":  round(sum(tier_pnls) / len(tier_pnls), 3),
            }
 
    return {
        "total_trades":        n,
        "win_rate":            round(win_rate, 3),
        "avg_pnl":             round(avg_pnl, 3),
        "avg_win":             round(avg_win, 3),
        "avg_loss":            round(avg_loss, 3),
        "best_trade":          round(best, 3),
        "worst_trade":         round(worst, 3),
        "total_pnl":           round(total_pnl, 3),
        "sharpe_ratio":        sharpe,
        "sortino_ratio":       sortino,
        "max_drawdown_pct":    round(max_dd, 3),
        "calmar_ratio":        calmar,
        "profit_factor":       profit_factor,
        "max_consec_wins":     max_consec_wins,
        "max_consec_losses":   max_consec_losses,
        "by_confidence":       conf_stats,
    }
 
 
def max_consecutive(pnls: list, positive: bool) -> int:
    max_streak = current = 0
    for p in pnls:
        if (positive and p > 0) or (not positive and p <= 0):
            current += 1
            max_streak = max(max_streak, current)
        else:
            current = 0
    return max_streak
 
 
def print_backtest_report(metrics: dict, trades: list):
    """Print formatted backtest report."""
    if not metrics:
        print("No resolved trades yet.")
        return
 
    print(f"\n{'='*55}")
    print(f"  BACKTEST REPORT — {datetime.utcnow().strftime('%Y-%m-%d')}")
    print(f"{'='*55}")
 
    print(f"\n📊 PERFORMANCE SUMMARY")
    print(f"  Total trades:      {metrics['total_trades']}")
    print(f"  Win rate:          {metrics['win_rate']*100:.1f}%")
    print(f"  Avg P&L/trade:     {metrics['avg_pnl']:+.2f}%")
    print(f"  Avg win:           {metrics['avg_win']:+.2f}%")
    print(f"  Avg loss:          {metrics['avg_loss']:+.2f}%")
    print(f"  Best trade:        {metrics['best_trade']:+.2f}%")
    print(f"  Worst trade:       {metrics['worst_trade']:+.2f}%")
    print(f"  Total P&L:         {metrics['total_pnl']:+.2f}%")
 
    print(f"\n📈 RISK METRICS")
    print(f"  Sharpe ratio:      {metrics['sharpe_ratio']:.3f}  {'✅ Good' if metrics['sharpe_ratio'] > 1.0 else ('⚠️ Moderate' if metrics['sharpe_ratio'] > 0.5 else '❌ Poor')}")
    print(f"  Sortino ratio:     {metrics['sortino_ratio']:.3f}  {'✅ Good' if metrics['sortino_ratio'] > 1.0 else ''}")
    print(f"  Max drawdown:      -{metrics['max_drawdown_pct']:.2f}%")
    print(f"  Calmar ratio:      {metrics['calmar_ratio']:.3f}  {'✅ Good' if metrics['calmar_ratio'] > 1.0 else ''}")
    print(f"  Profit factor:     {metrics['profit_factor']:.3f}  {'✅ Good' if metrics['profit_factor'] > 1.5 else ('⚠️ Moderate' if metrics['profit_factor'] > 1.0 else '❌ Poor')}")
 
    print(f"\n🎯 CONSISTENCY")
    print(f"  Max consec. wins:  {metrics['max_consec_wins']}")
    print(f"  Max consec. losses:{metrics['max_consec_losses']}")
 
    print(f"\n💼 BY CONFIDENCE TIER")
    for tier, stats in sorted(metrics["by_confidence"].items()):
        print(f"  {tier}:")
        print(f"    Trades: {stats['trades']} | Win: {stats['win_rate']*100:.1f}% | Avg: {stats['avg_pnl']:+.2f}%")
 
    # By pair
    pair_stats = {}
    for t in trades:
        pair = t["pair"]
        if pair not in pair_stats:
            pair_stats[pair] = []
        if t["pnl_pct"]:
            pair_stats[pair].append(float(t["pnl_pct"]))
 
    print(f"\n📋 BY PAIR")
    for pair, pnls in sorted(pair_stats.items(), key=lambda x: sum(x[1])/len(x[1]) if x[1] else 0, reverse=True):
        if pnls:
            wr  = len([p for p in pnls if p > 0]) / len(pnls)
            avg = sum(pnls) / len(pnls)
            print(f"  {pair:30} {len(pnls):3} trades | {wr*100:.0f}% | {avg:+.2f}%")
 
    print(f"\n{'='*55}")
 
    # Benchmark comparison
    print(f"\n🏆 BENCHMARK COMPARISON (annualized)")
    annual = metrics['avg_pnl'] * 208
    print(f"  This system:       {annual:+.1f}% estimated annual")
    print(f"  S&P 500 avg:       +10.5% per year")
    print(f"  VT (your base):    +8.0% per year")
    print(f"  60/40 portfolio:   +7.0% per year")
    if annual > 10.5:
        print(f"  ✅ Beating S&P 500")
    elif annual > 8.0:
        print(f"  ✅ Beating VT")
    else:
        print(f"  ⚠️ Underperforming benchmarks")
    print(f"{'='*55}\n")
 
 
def run_backtest():
    trades  = get_resolved_trades()
    metrics = calculate_metrics(trades)
    print_backtest_report(metrics, trades)
    return metrics
 
 
if __name__ == "__main__":
    run_backtest()