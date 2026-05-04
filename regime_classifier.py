"""
Regime Classifier — Option B
Detects whether market is in TRENDING or MEAN-REVERTING regime.
Momentum signals only work in trending regimes.
Pairs trading only works in mean-reverting regimes.
 
Uses:
- Hurst exponent (H < 0.5 = mean-reverting, H > 0.5 = trending)
- ADX (Average Directional Index) — trend strength
- VIX level — fear/calm
- Spread z-score from cointegration module
"""
 
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
 
# Thresholds
HURST_TRENDING      = 0.55   # H > 0.55 = trending
HURST_REVERTING     = 0.45   # H < 0.45 = mean-reverting
ADX_TRENDING        = 25     # ADX > 25 = strong trend
ZSCORE_ENTRY        = 1.5    # |z| > 1.5 = spread wide enough to trade
ZSCORE_EXIT         = 0.5    # |z| < 0.5 = spread converged, exit
 
 
def get_prices(ticker: str, days: int = 100) -> list:
    try:
        import yfinance as yf
        from config import YAHOO_MAP
        symbol = YAHOO_MAP.get(ticker, ticker)
        hist   = yf.Ticker(symbol).history(period=f"{days}d")
        if hist.empty:
            return []
        return hist["Close"].tolist()
    except Exception:
        return []
 
 
def hurst_exponent(prices: list, max_lag: int = 20) -> float:
    """
    Calculate Hurst exponent using R/S analysis.
    H < 0.5 → mean-reverting
    H = 0.5 → random walk
    H > 0.5 → trending
    """
    if len(prices) < max_lag * 2:
        return 0.5
 
    lags    = range(2, max_lag)
    tau     = []
    lag_arr = []
 
    for lag in lags:
        # Calculate R/S for this lag
        segments = len(prices) // lag
        if segments < 2:
            continue
 
        rs_list = []
        for i in range(segments):
            segment = prices[i*lag:(i+1)*lag]
            mean_s  = sum(segment) / len(segment)
            dev     = [p - mean_s for p in segment]
            cum_dev = []
            running = 0
            for d in dev:
                running += d
                cum_dev.append(running)
            R = max(cum_dev) - min(cum_dev)
            S = math.sqrt(sum(d**2 for d in dev) / len(dev))
            if S > 0:
                rs_list.append(R / S)
 
        if rs_list:
            tau.append(sum(rs_list) / len(rs_list))
            lag_arr.append(lag)
 
    if len(tau) < 3:
        return 0.5
 
    # Linear regression of log(RS) vs log(lag) → slope = H
    log_lag = [math.log(l) for l in lag_arr]
    log_tau = [math.log(t) for t in tau if t > 0]
    n       = min(len(log_lag), len(log_tau))
 
    if n < 3:
        return 0.5
 
    log_lag = log_lag[:n]
    log_tau = log_tau[:n]
 
    mean_x = sum(log_lag) / n
    mean_y = sum(log_tau) / n
    num    = sum((log_lag[i] - mean_x) * (log_tau[i] - mean_y) for i in range(n))
    den    = sum((log_lag[i] - mean_x) ** 2 for i in range(n))
 
    return round(num / den, 4) if den > 0 else 0.5
 
 
def adx(prices: list, period: int = 14) -> float:
    """
    Simplified ADX — measures trend strength regardless of direction.
    ADX > 25 = strong trend
    ADX < 20 = no trend / ranging
    """
    if len(prices) < period + 2:
        return 0.0
 
    # True Range approximation (no high/low, use close-to-close)
    tr_list = [abs(prices[i] - prices[i-1]) for i in range(1, len(prices))]
 
    # Smooth with EMA
    def ema(series, p):
        k = 2 / (p + 1)
        r = [series[0]]
        for v in series[1:]:
            r.append(v * k + r[-1] * (1 - k))
        return r
 
    atr_series = ema(tr_list, period)
 
    # Directional movement
    dm_plus  = [max(prices[i] - prices[i-1], 0) for i in range(1, len(prices))]
    dm_minus = [max(prices[i-1] - prices[i], 0) for i in range(1, len(prices))]
 
    di_plus_series  = ema(dm_plus, period)
    di_minus_series = ema(dm_minus, period)
 
    dx_list = []
    for i in range(len(atr_series)):
        if atr_series[i] > 0:
            di_plus  = 100 * di_plus_series[i] / atr_series[i]
            di_minus = 100 * di_minus_series[i] / atr_series[i]
            dsum     = di_plus + di_minus
            if dsum > 0:
                dx_list.append(100 * abs(di_plus - di_minus) / dsum)
 
    if not dx_list:
        return 0.0
 
    adx_val = sum(dx_list[-period:]) / min(period, len(dx_list))
    return round(adx_val, 2)
 
 
def get_vix() -> float:
    try:
        import yfinance as yf
        hist = yf.Ticker("^VIX").history(period="2d")
        if not hist.empty:
            return round(float(hist["Close"].iloc[-1]), 2)
    except Exception:
        pass
    return 20.0
 
 
def classify_pair_regime(ticker_a: str, ticker_b: str,
                          pair_name: str, zscore: float = None) -> dict:
    """
    Classify the current regime for a specific pair.
    Returns regime type and whether to trade.
    """
    prices_a = get_prices(ticker_a, 100)
    prices_b = get_prices(ticker_b, 100)
 
    if not prices_a or not prices_b:
        return {"pair": pair_name, "regime": "unknown",
                "trade": False, "reason": "no price data"}
 
    # Spread series
    n      = min(len(prices_a), len(prices_b))
    spread = [prices_a[-n+i] - prices_b[-n+i] for i in range(n)]
 
    # Hurst of spread — key metric
    h_spread = hurst_exponent(spread)
 
    # Hurst of individual assets
    h_a = hurst_exponent(prices_a)
    h_b = hurst_exponent(prices_b)
 
    # ADX of spread
    adx_spread = adx(spread)
 
    # VIX
    vix = get_vix()
 
    # Z-score entry signal
    zscore_entry = False
    if zscore is not None:
        zscore_entry = abs(zscore) >= ZSCORE_ENTRY
 
    # ── Regime classification ─────────────────────────────────
    if h_spread < HURST_REVERTING and adx_spread < ADX_TRENDING:
        regime = "mean_reverting"
        trade  = zscore_entry  # only if spread is wide enough
        reason = f"H={h_spread:.2f} (reverting) | ADX={adx_spread:.0f} (weak trend)"
 
    elif h_spread > HURST_TRENDING or adx_spread > ADX_TRENDING:
        regime = "trending"
        trade  = False  # pairs trading doesn't work in trending regime
        reason = f"H={h_spread:.2f} (trending) | ADX={adx_spread:.0f} — avoid pairs trading"
 
    else:
        regime = "neutral"
        trade  = zscore_entry and vix < 25  # only in calm neutral regime
        reason = f"H={h_spread:.2f} (neutral) | ADX={adx_spread:.0f} | VIX={vix}"
 
    return {
        "pair":       pair_name,
        "regime":     regime,
        "trade":      trade,
        "h_spread":   h_spread,
        "h_a":        h_a,
        "h_b":        h_b,
        "adx_spread": adx_spread,
        "vix":        vix,
        "zscore":     zscore,
        "reason":     reason,
    }
 
 
def run_regime_classifier(pairs: list, cointegration_results: list = None) -> dict:
    """
    Classify regime for all pairs.
    Uses z-scores from cointegration results if available.
    """
    print(f"\n[Regime Classifier] Classifying {len(pairs)} pairs...")
 
    # Build zscore lookup from cointegration results
    zscore_map = {}
    if cointegration_results:
        for r in cointegration_results:
            if r.get("zscore") is not None:
                zscore_map[r["pair"]] = r["zscore"]
 
    results = {}
    for pair in pairs:
        try:
            zscore = zscore_map.get(pair["name"])
            result = classify_pair_regime(
                pair["a"], pair["b"], pair["name"], zscore
            )
            results[pair["name"]] = result
 
            emoji = "✅" if result["trade"] else \
                    ("⚠️" if result["regime"] == "neutral" else "❌")
            print(f"    {emoji} {pair['name']:32} {result['regime']:15} "
                  f"H={result['h_spread']:.2f} ADX={result['adx_spread']:.0f} "
                  f"| {result['reason'][:35]}")
        except Exception as e:
            print(f"    [RC] Error {pair['name']}: {e}")
            results[pair["name"]] = {"regime": "error", "trade": True}
 
    tradeable = sum(1 for v in results.values() if v.get("trade"))
    print(f"    [RC] {tradeable}/{len(pairs)} pairs in tradeable regime")
    return results
 
 
def apply_regime_classification(signal_results: list,
                                  regime_classifications: dict) -> list:
    """
    Filter signals based on regime classification.
    Only pass signals where the pair is in mean-reverting regime
    AND the spread z-score is at entry threshold.
    """
    filtered = []
    for signal in signal_results:
        pair_name = signal["pair"]
        rc        = regime_classifications.get(pair_name, {})
 
        if not rc.get("trade", True):
            regime = rc.get("regime", "unknown")
            reason = rc.get("reason", "")
            print(f"    [RC] SKIP {pair_name} — {regime} | {reason[:50]}")
            continue
 
        # Attach regime info to signal
        adj = dict(signal)
        adj["regime_type"] = rc.get("regime", "unknown")
        adj["hurst"]       = rc.get("h_spread")
        filtered.append(adj)
 
    return filtered
 
 
if __name__ == "__main__":
    from config import PAIRS
    results = run_regime_classifier(PAIRS[:5])
    for pair, data in results.items():
        print(f"{pair}: {data['regime']} | trade={data['trade']}")