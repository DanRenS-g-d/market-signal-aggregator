"""
Hierarchical Risk Parity (HRP) Portfolio Optimizer
Uses Riskfolio-Lib to:
1. Convert prices to returns
2. Cluster assets by correlation structure
3. Select one asset per cluster (maximum diversification)
4. Weight by inverse volatility within clusters
5. Output capital allocation per signal
 
Integrates with existing signal pipeline:
- Input: list of active signal tickers
- Output: dict of ticker -> allocation percentage
"""
 
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
 
MIN_HISTORY_DAYS = 60    # minimum days of return history
MAX_WEIGHT       = 0.35  # no single asset > 35% of portfolio
MAX_WEIGHT_BONDS = 0.20  # bonds capped lower — we want equity exposure
MIN_WEIGHT       = 0.05  # no single asset < 5% (too small to be meaningful)
 
BOND_TICKERS = {"TLT", "IEF", "HYG", "EMB", "SHY", "AGG", "BND"}
 
 
def get_returns(tickers: list, days: int = 252) -> "pd.DataFrame | None":
    """Fetch price history and convert to returns for all active tickers."""
    try:
        import yfinance as yf
        import pandas as pd
        from config import YAHOO_MAP
 
        price_data = {}
        for ticker in tickers:
            symbol = YAHOO_MAP.get(ticker, ticker)
            try:
                hist = yf.Ticker(symbol).history(period=f"{days}d")
                if not hist.empty and len(hist) >= MIN_HISTORY_DAYS:
                    price_data[ticker] = hist["Close"]
            except Exception as e:
                print(f"    [HRP] No data for {ticker}: {e}")
 
        if len(price_data) < 2:
            return None
 
        prices  = pd.DataFrame(price_data).dropna()
        returns = prices.pct_change().dropna()
 
        print(f"    [HRP] Returns matrix: {len(returns)} days × {len(returns.columns)} assets")
        return returns
 
    except Exception as e:
        print(f"    [HRP] Error fetching returns: {e}")
        return None
 
 
def run_hrp(tickers: list) -> dict:
    """
    Run HRP optimization on active tickers.
    Returns dict: ticker -> weight (0-1, sums to 1)
    """
    try:
        import riskfolio as rp
        import pandas as pd
        import numpy as np
 
        returns = get_returns(tickers)
        if returns is None or returns.shape[1] < 2:
            # Fallback: equal weight
            n = len(tickers)
            return {t: round(1/n, 3) for t in tickers}
 
        # Build HRP portfolio
        port = rp.HCPortfolio(returns=returns)
 
        # Fit the model
        w = port.optimization(
            model="HRP",
            codependence="pearson",
            rm="MV",           # risk measure: minimum variance
            rf=0,              # risk-free rate
            linkage="ward",    # Ward linkage for clustering
            max_k=10,
            leaf_order=True,
        )
 
        if w is None or w.empty:
            n = len(tickers)
            return {t: round(1/n, 3) for t in tickers}
 
        # Extract weights
        weights = {}
        for ticker in returns.columns:
            if ticker in w.index:
                raw_w = float(w.loc[ticker, "weights"])
                # Apply min/max constraints — bonds capped lower
                cap = MAX_WEIGHT_BONDS if ticker in BOND_TICKERS else MAX_WEIGHT
                weights[ticker] = round(max(MIN_WEIGHT, min(cap, raw_w)), 3)
 
        # Add any tickers not in optimization (equal share of remainder)
        missing = [t for t in tickers if t not in weights]
        if missing:
            share = round(MIN_WEIGHT, 3)
            for t in missing:
                weights[t] = share
 
        # Normalize to sum to 1
        total = sum(weights.values())
        if total > 0:
            weights = {k: round(v/total, 3) for k, v in weights.items()}
 
        return weights
 
    except Exception as e:
        print(f"    [HRP] Optimization error: {e} — falling back to equal weight")
        n = max(len(tickers), 1)
        return {t: round(1/n, 3) for t in tickers}
 
 
def get_cluster_info(tickers: list) -> dict:
    """Get cluster assignments for display in Telegram."""
    try:
        import riskfolio as rp
        import pandas as pd
        import numpy as np
        from scipy.cluster.hierarchy import fcluster, linkage
        from scipy.spatial.distance import squareform
 
        returns = get_returns(tickers, days=120)
        if returns is None:
            return {}
 
        corr   = returns.corr()
        dist   = np.sqrt(0.5 * (1 - corr))
        np.fill_diagonal(dist.values, 0)
 
        condensed = squareform(dist.values)
        Z         = linkage(condensed, method="ward")
 
        # Auto-select k clusters
        k = min(max(2, len(tickers) // 3), 5)
        labels = fcluster(Z, k, criterion="maxclust")
 
        clusters = {}
        for ticker, label in zip(returns.columns, labels):
            cluster_name = f"Cluster {label}"
            if cluster_name not in clusters:
                clusters[cluster_name] = []
            clusters[cluster_name].append(ticker)
 
        return clusters
 
    except Exception as e:
        print(f"    [HRP] Cluster error: {e}")
        return {}
 
 
def apply_hrp_to_signals(signal_results: list) -> list:
    """
    Main integration point with signal pipeline.
    Takes active signals, runs HRP, attaches allocation % to each signal.
    """
    non_neutral = [r for r in signal_results if r["signal"] != "neutral"]
 
    if not non_neutral:
        return signal_results
 
    # Get active tickers
    active_tickers = []
    for r in non_neutral:
        ticker = r["ticker_a"] if r["signal"] == "long_a" else r["ticker_b"]
        if ticker not in active_tickers:
            active_tickers.append(ticker)
 
    if len(active_tickers) < 2:
        # Single ticker — full allocation
        for r in signal_results:
            if r["signal"] != "neutral":
                r["hrp_weight"]      = 1.0
                r["hrp_alloc_pct"]   = 100
        return signal_results
 
    print(f"    [HRP] Optimizing allocation for: {active_tickers}")
    weights  = run_hrp(active_tickers)
    clusters = get_cluster_info(active_tickers)
 
    print(f"    [HRP] Weights: {weights}")
 
    # Attach weights to signals
    for r in signal_results:
        if r["signal"] == "neutral":
            continue
        ticker = r["ticker_a"] if r["signal"] == "long_a" else r["ticker_b"]
        weight = weights.get(ticker, 1/len(active_tickers))
        r["hrp_weight"]    = weight
        r["hrp_alloc_pct"] = int(weight * 100)
 
        # Find cluster
        for cluster_name, members in clusters.items():
            if ticker in members:
                r["hrp_cluster"] = cluster_name
                break
 
    return signal_results
 
 
def format_hrp_for_telegram(signal_results: list) -> str:
    """Format HRP allocation summary for Telegram."""
    non_neutral = [r for r in signal_results
                   if r["signal"] != "neutral" and "hrp_weight" in r]
 
    if not non_neutral or len(non_neutral) < 2:
        return ""
 
    lines = []
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("⚖️ <b>HRP CAPITAL ALLOCATION</b>")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("<i>Hierarchical Risk Parity — uncorrelated returns</i>")
    lines.append("")
 
    # Sort by allocation descending
    sorted_signals = sorted(non_neutral,
                           key=lambda x: x.get("hrp_weight", 0), reverse=True)
 
    for r in sorted_signals:
        ticker = r["ticker_a"] if r["signal"] == "long_a" else r["ticker_b"]
        pct    = r.get("hrp_alloc_pct", 0)
        cluster = r.get("hrp_cluster", "")
        bar    = "█" * (pct // 10) + "░" * (10 - pct // 10)
        cluster_str = f" ({cluster})" if cluster else ""
        lines.append(f"<code>{bar}</code> <b>{ticker}</b>: {pct}%{cluster_str}")
 
    lines.append("")
    lines.append("<i>Weights optimized to minimize correlation between positions</i>")
    return "\n".join(lines)
 
 
if __name__ == "__main__":
    # Test with sample tickers
    test_tickers = ["EC", "CIB", "AVAL", "EWZ", "EWW", "TLT"]
    print(f"Testing HRP with: {test_tickers}")
    weights = run_hrp(test_tickers)
    print(f"\nHRP Weights:")
    for ticker, w in sorted(weights.items(), key=lambda x: x[1], reverse=True):
        bar = "█" * int(w * 20)
        print(f"  {ticker:12} {bar} {w*100:.1f}%")
 
    clusters = get_cluster_info(test_tickers)
    print(f"\nClusters:")
    for name, members in clusters.items():
        print(f"  {name}: {members}")