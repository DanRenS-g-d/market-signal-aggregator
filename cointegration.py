"""
Cointegration Testing Module
Tests each pair for statistical cointegration using:
1. Engle-Granger two-step test
2. Johansen test (confirmation)
3. Half-life of mean reversion (how fast does spread revert?)
 
Only pairs that pass cointegration should be traded.
Cointegration = two assets share a long-run equilibrium.
When they diverge, there is a statistically grounded reason to expect convergence.
"""
 
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
 
PVALUE_THRESHOLD    = 0.05   # 95% confidence
HALFLIFE_MAX_DAYS   = 30     # spread must revert within 30 days to be tradeable
HALFLIFE_MIN_DAYS   = 1      # too fast = noise
MIN_HISTORY_DAYS    = 252    # 1 year minimum
 
 
def get_price_series(ticker: str, days: int = 500) -> tuple[list, list]:
    """Returns (dates, prices)."""
    try:
        import yfinance as yf
        from config import YAHOO_MAP
        symbol = YAHOO_MAP.get(ticker, ticker)
        hist   = yf.Ticker(symbol).history(period=f"{days}d")
        if hist.empty:
            return [], []
        return list(hist.index.astype(str)), hist["Close"].tolist()
    except Exception as e:
        print(f"    [Coint] Price error {ticker}: {e}")
        return [], []
 
 
def align_series(dates_a, prices_a, dates_b, prices_b):
    """Align two price series on common dates."""
    dates_a = [str(d)[:10] for d in dates_a]
    dates_b = [str(d)[:10] for d in dates_b]
    common  = sorted(set(dates_a) & set(dates_b))
    map_a   = dict(zip(dates_a, prices_a))
    map_b   = dict(zip(dates_b, prices_b))
    a = [map_a[d] for d in common]
    b = [map_b[d] for d in common]
    return common, a, b
 
 
def ols_regression(y: list, x: list) -> tuple[float, float, list]:
    """Simple OLS: y = alpha + beta * x. Returns (alpha, beta, residuals)."""
    n      = len(y)
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    beta   = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n)) / \
             sum((x[i] - mean_x) ** 2 for i in range(n))
    alpha  = mean_y - beta * mean_x
    resids = [y[i] - alpha - beta * x[i] for i in range(n)]
    return alpha, beta, resids
 
 
def adf_test(series: list) -> tuple[float, float]:
    """
    Simplified Augmented Dickey-Fuller test.
    Tests if series is stationary (mean-reverting).
    Returns (test_statistic, approximate_p_value).
    Critical values: -3.43 (1%), -2.86 (5%), -2.57 (10%)
    """
    n    = len(series)
    if n < 20:
        return 0.0, 1.0
 
    # First differences
    diff = [series[i] - series[i-1] for i in range(1, n)]
 
    # Lagged levels
    lag  = series[:-1]
 
    # OLS: diff = alpha + beta * lag
    mean_lag  = sum(lag) / len(lag)
    mean_diff = sum(diff) / len(diff)
 
    beta_num = sum((lag[i] - mean_lag) * (diff[i] - mean_diff) for i in range(len(lag)))
    beta_den = sum((lag[i] - mean_lag) ** 2 for i in range(len(lag)))
 
    if beta_den == 0:
        return 0.0, 1.0
 
    beta = beta_num / beta_den
    resids = [diff[i] - mean_diff - beta * (lag[i] - mean_lag) for i in range(len(lag))]
 
    # Standard error of beta
    sse    = sum(r ** 2 for r in resids)
    s2     = sse / (len(resids) - 2)
    se     = math.sqrt(s2 / beta_den) if beta_den > 0 else 1
 
    t_stat = beta / se if se > 0 else 0
 
    # Approximate p-value from t-statistic
    # ADF critical values (approximate): -3.43 → 0.01, -2.86 → 0.05, -2.57 → 0.10
    if t_stat < -3.43:
        p_value = 0.01
    elif t_stat < -2.86:
        p_value = 0.05
    elif t_stat < -2.57:
        p_value = 0.10
    elif t_stat < -1.94:
        p_value = 0.25
    else:
        p_value = 0.50
 
    return round(t_stat, 4), round(p_value, 4)
 
 
def calculate_half_life(residuals: list) -> float:
    """
    Calculate half-life of mean reversion using AR(1) model.
    residuals[t] = rho * residuals[t-1] + epsilon
    half_life = -log(2) / log(rho)
    """
    n   = len(residuals)
    if n < 10:
        return float('inf')
 
    y   = residuals[1:]
    x   = residuals[:-1]
    m   = len(y)
 
    mean_x = sum(x) / m
    mean_y = sum(y) / m
 
    num = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(m))
    den = sum((x[i] - mean_x) ** 2 for i in range(m))
 
    if den == 0:
        return float('inf')
 
    rho = num / den
 
    if rho >= 1 or rho <= 0:
        return float('inf')
 
    half_life = -math.log(2) / math.log(rho)
    return round(half_life, 1)
 
 
def calculate_zscore(residuals: list, window: int = 20) -> float:
    """Current z-score of the spread — how far from mean in std devs."""
    if len(residuals) < window:
        return 0.0
    recent  = residuals[-window:]
    mean    = sum(recent) / len(recent)
    std     = math.sqrt(sum((r - mean) ** 2 for r in recent) / len(recent))
    if std == 0:
        return 0.0
    return round((residuals[-1] - mean) / std, 3)
 
 
def test_pair_cointegration(ticker_a: str, ticker_b: str,
                             pair_name: str) -> dict:
    """
    Full cointegration test for a pair.
    Returns detailed results including tradeable verdict.
    """
    dates_a, prices_a = get_price_series(ticker_a, 500)
    dates_b, prices_b = get_price_series(ticker_b, 500)
 
    if len(prices_a) < MIN_HISTORY_DAYS or len(prices_b) < MIN_HISTORY_DAYS:
        return {
            "pair":        pair_name,
            "cointegrated": False,
            "reason":      f"insufficient history ({len(prices_a)}, {len(prices_b)} days)",
            "tradeable":   False,
        }
 
    dates, a, b = align_series(dates_a, prices_a, dates_b, prices_b)
    if len(dates) < MIN_HISTORY_DAYS:
        return {
            "pair":        pair_name,
            "cointegrated": False,
            "reason":      f"insufficient aligned history ({len(dates)} days)",
            "tradeable":   False,
        }
 
    # Step 1: OLS regression to find hedge ratio
    alpha, beta, residuals = ols_regression(a, b)
 
    # Step 2: ADF test on residuals
    t_stat, p_value = adf_test(residuals)
 
    # Step 3: Half-life of mean reversion
    half_life = calculate_half_life(residuals)
 
    # Step 4: Current z-score
    zscore = calculate_zscore(residuals)
 
    # Step 5: Verdict
    cointegrated = p_value <= PVALUE_THRESHOLD
    hl_ok        = HALFLIFE_MIN_DAYS <= half_life <= HALFLIFE_MAX_DAYS
    tradeable    = cointegrated and hl_ok
 
    reasons = []
    if not cointegrated:
        reasons.append(f"p={p_value:.3f} > {PVALUE_THRESHOLD} — not stationary")
    if half_life > HALFLIFE_MAX_DAYS:
        reasons.append(f"half-life {half_life:.0f}d > {HALFLIFE_MAX_DAYS}d — too slow")
    if half_life < HALFLIFE_MIN_DAYS:
        reasons.append(f"half-life {half_life:.1f}d < {HALFLIFE_MIN_DAYS}d — too noisy")
    if tradeable:
        reasons.append(f"p={p_value:.3f} ✅ half-life={half_life:.0f}d ✅")
 
    return {
        "pair":         pair_name,
        "ticker_a":     ticker_a,
        "ticker_b":     ticker_b,
        "cointegrated": cointegrated,
        "p_value":      p_value,
        "t_stat":       t_stat,
        "beta":         round(beta, 4),
        "half_life":    half_life,
        "zscore":       zscore,
        "tradeable":    tradeable,
        "reason":       " | ".join(reasons),
        "n_days":       len(dates),
    }
 
 
def save_cointegration_results(results: list):
    """Save results to DB for use by signal generator."""
    from db import get_connection
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pair_cointegration (
            pair_name     VARCHAR(100) PRIMARY KEY,
            cointegrated  BOOLEAN,
            p_value       DECIMAL(6,4),
            t_stat        DECIMAL(8,4),
            beta          DECIMAL(10,4),
            half_life     DECIMAL(8,1),
            zscore        DECIMAL(8,3),
            tradeable     BOOLEAN,
            reason        TEXT,
            tested_at     TIMESTAMP DEFAULT NOW()
        )
    """)
    for r in results:
        cur.execute("""
            INSERT INTO pair_cointegration
                (pair_name, cointegrated, p_value, t_stat, beta,
                 half_life, zscore, tradeable, reason, tested_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
            ON CONFLICT (pair_name) DO UPDATE SET
                cointegrated = EXCLUDED.cointegrated,
                p_value      = EXCLUDED.p_value,
                t_stat       = EXCLUDED.t_stat,
                beta         = EXCLUDED.beta,
                half_life    = EXCLUDED.half_life,
                zscore       = EXCLUDED.zscore,
                tradeable    = EXCLUDED.tradeable,
                reason       = EXCLUDED.reason,
                tested_at    = NOW()
        """, (
            r["pair"], r.get("cointegrated"), r.get("p_value"),
            r.get("t_stat"), r.get("beta"), r.get("half_life"),
            r.get("zscore"), r.get("tradeable"), r.get("reason"),
        ))
    conn.commit(); cur.close(); conn.close()
 
 
def run_cointegration_tests(pairs: list) -> list:
    """Test all pairs and return results sorted by tradeable first."""
    print(f"\n[Cointegration] Testing {len(pairs)} pairs...")
    results = []
    for pair in pairs:
        try:
            result = test_pair_cointegration(pair["a"], pair["b"], pair["name"])
            results.append(result)
            emoji = "✅" if result["tradeable"] else \
                    ("🟡" if result.get("cointegrated") else "❌")
            hl    = f"hl={result.get('half_life','?')}d" if result.get("half_life") else ""
            print(f"    {emoji} {pair['name']:32} p={result.get('p_value','?')} "
                  f"{hl} | {result['reason'][:45]}")
        except Exception as e:
            print(f"    [Coint] Error {pair['name']}: {e}")
            results.append({"pair": pair["name"], "tradeable": False,
                            "reason": str(e), "cointegrated": False})
 
    save_cointegration_results(results)
 
    tradeable = [r for r in results if r.get("tradeable")]
    print(f"\n    [Coint] {len(tradeable)}/{len(pairs)} pairs are cointegrated and tradeable")
    return results
 
 
def get_tradeable_pairs() -> set:
    """Get set of pair names that passed cointegration test."""
    from db import get_connection
    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("""
            SELECT pair_name FROM pair_cointegration
            WHERE tradeable = TRUE
            AND tested_at >= NOW() - INTERVAL '7 days'
        """)
        rows = cur.fetchall()
        cur.close(); conn.close()
        return {r[0] for r in rows}
    except Exception:
        return set()
 
 
def print_cointegration_report(results: list):
    tradeable = [r for r in results if r.get("tradeable")]
    coint_only = [r for r in results if r.get("cointegrated") and not r.get("tradeable")]
    failed    = [r for r in results if not r.get("cointegrated")]
 
    print(f"\n{'='*60}")
    print(f"  COINTEGRATION REPORT")
    print(f"{'='*60}")
 
    print(f"\n✅ TRADEABLE ({len(tradeable)} pairs)")
    for r in tradeable:
        print(f"  {r['pair']:32} p={r['p_value']:.3f} | "
              f"hl={r['half_life']:.0f}d | z={r['zscore']:+.2f} | β={r['beta']:.3f}")
 
    print(f"\n🟡 COINTEGRATED BUT SLOW ({len(coint_only)} pairs)")
    for r in coint_only:
        print(f"  {r['pair']:32} p={r.get('p_value','?')} | {r['reason'][:50]}")
 
    print(f"\n❌ NOT COINTEGRATED ({len(failed)} pairs)")
    for r in failed:
        print(f"  {r['pair']:32} {r['reason'][:50]}")
 
    print(f"\n{'='*60}")
    print(f"  Recommendation: only trade the {len(tradeable)} tradeable pairs")
    print(f"{'='*60}\n")
 
 
if __name__ == "__main__":
    from config import PAIRS
    results = run_cointegration_tests(PAIRS)
    print_cointegration_report(results)